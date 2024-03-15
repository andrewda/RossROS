from kademlia.network import Server
import asyncio
import logging


# Turn down verbosity of kademlia
kademlia_logger = logging.getLogger('kademlia')
kademlia_logger.setLevel(logging.ERROR)


async def start_node(port, bootstrap_node=None):
  server = Server()
  await server.listen(port)
  if bootstrap_node:
      await server.bootstrap([bootstrap_node])
  return server


class NetBus:
    """
    Bus class using DHT for state storage
    """

    def __init__(self, server, name, initial_message=None):
        self.server = server
        self.name = name

        if initial_message is not None:
            loop = asyncio.get_event_loop()
            loop.create_task(self.set_message(initial_message))

    async def get_message(self, _name=None):
        # print(f'\t{self.name} - getting message')
        message = await self.server.get(self.name)
        # print(f'\t{self.name} - retrieved message: {message}')
        return message

    async def set_message(self, message, _name=None):
        # print(f'\t{self.name} - setting message to {message}')
        await self.server.set(self.name, message)
