import asyncio
import logging
from typing import Dict, List
from bleak import BleakScanner
from bleak.exc import BleakDBusError
from bluetti_mqtt.core import DeviceCommand
from .client import BluetoothClient


class MultiDeviceManager:
    clients: Dict[str, BluetoothClient]

    def __init__(self, addresses: List[str]):
        self.addresses = addresses
        self.clients = {}

    async def run(self):
        logging.info(f'Connecting to clients: {self.addresses}')

        # Perform a blocking scan just to speed up initial connect
        scanner = BleakScanner()
        scan_successful = False
        
        # Try to scan multiple times if adapter is busy
        for i in range(5):
            try:
                await scanner.start()
                await asyncio.sleep(5.0)
                await scanner.stop()
                scan_successful = True
                logging.debug('Bluetooth scan completed successfully')
                break
            except BleakDBusError as e:
                if 'org.bluez.Error.InProgress' in str(e):
                    logging.warning(f'Scan in progress, waiting to retry ({i+1}/5)...')
                    await asyncio.sleep(5.0)
                else:
                    logging.error(f'Bluetooth scan error: {e}')
                    break
        
        if not scan_successful:
            logging.warning('Scan failed, will attempt direct connection to devices')

        # Start client loops
        # Use discovered device if available, otherwise fallback to address string
        discovered_map = {d.address: d for d in scanner.discovered_devices}
        
        self.clients = {}
        for addr in self.addresses:
            if addr in discovered_map:
                logging.info(f'Using discovered device for {addr}')
                self.clients[addr] = BluetoothClient(discovered_map[addr])
            else:
                logging.info(f'Device {addr} not found in scan, using address string')
                self.clients[addr] = BluetoothClient(addr)
        await asyncio.gather(*[c.run() for c in self.clients.values()])

    def is_ready(self, address: str):
        if address in self.clients:
            return self.clients[address].is_ready
        else:
            return False

    def get_name(self, address: str):
        if address in self.clients:
            return self.clients[address].name
        else:
            raise Exception('Unknown address')

    async def perform(self, address: str, command: DeviceCommand):
        if address in self.clients:
            return await self.clients[address].perform(command)
        else:
            raise Exception('Unknown address')

    async def perform_nowait(self, address: str, command: DeviceCommand):
        if address in self.clients:
            await self.clients[address].perform_nowait(command)
        else:
            raise Exception('Unknown address')
