#!/usr/bin/python3
"""
This file (in conjunction with rr_networking_node1.py) demonstrates basic communication
between two RossROS network nodes. This node (node2) listens for signals published by
node1, multiplies them together, and publishes the result.
"""

# Add parent directory to Python path
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import asyncio
import logging
import math
import time

import rossros_asyncio as rr
import rossros_networking as rrn

logging.getLogger().setLevel(logging.INFO)

async def node2():

    # Start second node, bootstrapping from first node
    node = rrn.Client('127.0.0.1', 9800)


    # This function multiplies two inputs together
    def mult(a, b):
        return (a if a is not None else 0) * (b if b is not None else 0)


    # Initiate data and termination busses
    bSquare = rrn.NetBus(node, "/square_wave") # Published by node1
    bSawtooth = rrn.NetBus(node, "/sawtooth_wave") # Published by node1
    bMultiplied = rr.Bus(node, "/combined_wave")
    bTerminate = rr.Bus(0, "/termination")


    # Wrap the multiplier function into a consumer-producer
    multiplyWaves = rr.ConsumerProducer(
        mult,  # function that will process data
        (bSquare, bSawtooth),  # input data buses
        bMultiplied,  # output data bus
        0.01,  # delay between data control cycles
        bTerminate,  # bus to watch for termination signal
        "Multiply Waves")


    # Make a printer that returns the most recent wave and product values
    printBuses = rr.Printer(
        (bSquare, bSawtooth, bMultiplied, bTerminate),  # input data buses
        # bMultiplied,      # input data buses
        0.25,  # delay between printing cycles
        bTerminate,  # bus to watch for termination signal
        "Print raw and derived data",  # Name of printer
        "Data bus readings are: ")  # Prefix for output

    # Make a timer (a special kind of producer) that turns on the termination
    # bus when it triggers
    terminationTimer = rr.Timer(
        bTerminate,  # Output data bus
        10,  # Duration
        0.01,  # Delay between checking for termination time
        bTerminate,  # Bus to check for termination signal
        "Termination timer")  # Name of this timer


    # Create a list of producer-consumers to execute concurrently
    producer_consumer_list = [multiplyWaves, printBuses, terminationTimer]

    # Execute the list of producer-consumers concurrently
    await rr.gather(producer_consumer_list)


asyncio.run(node2())
