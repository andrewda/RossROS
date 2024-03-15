from kademlia.network import Server
import asyncio

# Function to start a node
async def start_node(port, bootstrap_node=None):
  server = Server()
  await server.listen(port)
  if bootstrap_node:
      await server.bootstrap([bootstrap_node])
  return server

# Function to store a value in the network
async def store_value(server, key, value):
  await server.set(key, value)

# Function to retrieve a value from the network
async def retrieve_value(server, key):
  result = await server.get(key)
  return result

# Example usage
async def run_demo():
  # Start the first node (bootstrap node)
  node1 = await start_node(8468)
  print("Node 1 started")

  # Start a second node and connect it to the first node
  node2 = await start_node(8469, ('localhost', 8468))
  print("Node 2 connected to Node 1")

  # Store a value in the network
  await store_value(node2, "key", "This is a test value")
  print("Value stored in the network")

  # Retrieve the value from the network using the second node
  value = await retrieve_value(node2, "key")
  print(f"Retrieved value from the network: {value}")

  value = await retrieve_value(node1, "key")
  print(f"Retrieved value from the network: {value}")

# Run the demo
asyncio.run(run_demo())
