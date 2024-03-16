import asyncio
import json
import logging
import socket
import threading
from typing import Any, Tuple


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.state = {}

    async def handle_client(self, reader, writer):
        while True:
            data = await reader.read(1024)
            if not data:
                break
            command = json.loads(data.decode('utf-8'))

            if command['action'] == 'set':
                self.set(command['key'], command['value'])
                response = {'status': 'OK'}
            elif command['action'] == 'get':
                value = await self.get(command['key'])
                response = {'status': 'OK', 'value': value}
            else:
                response = {'status': 'ERROR', 'message': 'Unknown command'}


            writer.write(json.dumps(response).encode('utf-8'))
            await writer.drain()
        writer.close()

    async def set(self, key, value):
        self.state[key] = value

    async def get(self, key):
        return self.state.get(key, None)

    async def run(self):
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        print(f'Serving on {addr}')

        async with server:
            await server.serve_forever()

class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def send_command(self, command):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        writer.write(json.dumps(command).encode('utf-8'))
        await writer.drain()
        response = await reader.read(1024)
        writer.close()
        await writer.wait_closed()
        return json.loads(response.decode('utf-8'))

    async def set(self, key, value):
        command = {'action': 'set', 'key': key, 'value': value}
        await self.send_command(command)

    async def get(self, key):
        command = {'action': 'get', 'key': key}
        response = await self.send_command(command)
        return response.get('value')


class NetBus:
    """
    Bus class using network for state storage
    """

    def __init__(self, server, name, initial_message=None):
        self.server = server
        self.name = name

        if initial_message is not None:
            loop = asyncio.get_event_loop()
            loop.create_task(self.set_message(initial_message))

    async def get_message(self, _name=None):
        message = await self.server.get(self.name)
        return message

    async def set_message(self, message, _name=None):
        await self.server.set(self.name, message)
