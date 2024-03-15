#!/usr/bin/python3
"""
This file (in conjunction with rr_networking_node2.py) demonstrates basic communication
between two RossROS network nodes. This node (node1) generates and publishes a square
wave signal and a sawtooth signal to the network.
"""

# Add parent directory to Python path
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import rossros_asyncio as rr
import rossros_networking as rrn
import logging
import time
import math
import asyncio

logging.getLogger().setLevel(logging.INFO)

async def node1():

    # Start first node
    node = await rrn.start_node(5000)


    # Create two signal-generation functions

    # This function outputs a square wave that steps between +/- 1
    # every second
    def square():
        return (2 * math.floor(time.time() % 2)) - 1


    # This function counts up from zero to 1 every second
    def sawtooth():
        return time.time() % 1  # "%" is the modulus operator


    # Initiate data and termination busses
    bSquare = rrn.NetBus(node, "/square_wave", square())
    bSawtooth = rrn.NetBus(node, "/sawtooth_wave", sawtooth())


    # Wrap the square wave signal generator into a producer
    readSquare = rr.Producer(
        square,  # function that will generate data
        bSquare,  # output data bus
        0.05,  # delay between data generation cycles
        name="Read square wave signal")

    # Wrap the sawtooth wave signal generator into a producer
    readSawtooth = rr.Producer(
        sawtooth,  # function that will generate data
        bSawtooth,  # output data bus
        0.05,  # delay between data generation cycles
        name="Read sawtooth wave signal")


    # Create a list of producer-consumers to execute concurrently
    producer_consumer_list = [readSquare, readSawtooth]

    # Execute the list of producer-consumers concurrently
    await rr.gather(producer_consumer_list)


asyncio.run(node1())
