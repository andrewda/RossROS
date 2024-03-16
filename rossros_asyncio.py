#!/usr/bin/python3
"""
This file modifies RossROS to use cooperative multitasking (via the asyncio package)
rather than preemptive multitasking (via concurrent.futures)

--

The RossROS AsyncIO package acts as a transparent wrapper on top of RossROS:
The user syntax for both the base RossROS package and this modification are the same, and you can replace

import rossros

with

import rossros_asyncio

and expect your code to run as before (assuming that you haven't incorporated any extra dependencies on
the threading architecture from concurrent.futures).

While running RossROS AsyncIO, you can include calls to "await.sleep" within the consumer and producer functions
(but note that any such calls will stack with the loop delay time, so that you should decrease the loop delay
to keep the same overall execution frequency).

--

Under the hood, RossROS AsyncIO makes three changes to RossROS:

First, it replaces the Bus class with a version that does not use locking code (which is no longer necessary
because switching behavior is explicitly handled by the code structure).

Second, it replaces the __call__ method for all ConsumerProducers with a version that is aware of the asyncio
task-switching architecture.

Third, it replaces the runConcurrently function with a version that uses the asyncio paradigm.
"""

import asyncio
import concurrent.futures
import logging
import time

import rossros as rr
from logdecorator import log_on_end, log_on_error, log_on_start
from readerwriterlock import rwlock

DEBUG = logging.DEBUG
logging_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=logging_format, level=logging.INFO,
                    datefmt="%H:%M:%S")

""" First Change: For asyncio, locking is handled manually, so the Bus class does not the the RWLock code"""


class Bus:
    """
    Redefined bus class that removes the RW lock code
    """

    def __init__(self, initial_message=0, name="Unnamed Bus"):
        self.message = initial_message
        self.name = name

    async def get_message(self, _name):
        message = self.message
        return message

    async def set_message(self, message, _name):
        self.message = message


async def maybe_await(future, *args, **kwargs):
    """
    Function that checks if a future is a coroutine and awaits it if it is
    """
    if asyncio.iscoroutinefunction(future):
        return await future(*args, **kwargs)
    else:
        return future(*args, **kwargs)


""""
Second Change: the __call__ method for ConsumerProducer and its child classes needs to be an async function
and have an "await asyncio.sleep" call instead of time.sleep.
"""


class ConsumerProducer(rr.ConsumerProducer):

    @log_on_start(DEBUG, "{self.name:s}: Starting consumer-producer service")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while closing down consumer-producer")
    @log_on_end(DEBUG, "{self.name:s}: Closing down consumer-producer service")
    async def __call__(self):

        while True:

            # Check if the loop should terminate
            # termination_value = self.termination_buses[0].get_message(self.name)
            if await self.checkTerminationBuses():
                break

            # Collect all of the values from the input buses into a list
            input_values = await self.collectBusesToValues(self.input_buses)

            # Get the output value or tuple of values corresponding to the inputs
            output_values = self.consumer_producer_function(*input_values)

            # Deal the values into the output buses
            await self.dealValuesToBuses(output_values, self.output_buses)

            # Pause for set amount of time
            await asyncio.sleep(self.delay)


    @log_on_start(DEBUG, "{self.name:s}: Starting collecting bus values into list")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while collecting bus values")
    @log_on_end(DEBUG, "{self.name:s}: Finished collecting bus values")
    async def collectBusesToValues(self, buses):

        # Wrap buses in a tuple if it isn't one already
        buses = rr.ensureTuple(buses)

        # Create a list for storing the values in the buses
        values = []

        # Loop over the buses, recording their values
        for p in buses:
            message = await maybe_await(p.get_message, self.name)
            values.append(message)

        return values


    # Take in  a tuple of values and a tuple of buses, and deal the values
    # into the buses
    @log_on_start(DEBUG, "{self.name:s}: Starting dealing values into buses")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while dealing values into buses")
    @log_on_end(DEBUG, "{self.name:s}: Finished dealing values into buses")
    async def dealValuesToBuses(self, values, buses):

        # Wrap buses in a tuple if it isn't one already
        buses = rr.ensureTuple(buses)

        # Handle different combinations of bus and value counts

        # If there is only one bus, then the values should be treated as a
        # single entity, and wrapped into a tuple for the dealing process
        if len(buses) == 1:
            values = (values, )
        # If there are multiple buses
        else:
            # If the values are already presented as a tuple, leave them
            if isinstance(values, tuple):
                pass
            # If the values are not already presented as a tuple,
            # Make a tuple with one entry per bus, all of which are the
            # equal to the input values
            else:
                values = tuple([values]*len(buses))

        for idx, v in enumerate(values):
            await maybe_await(buses[idx].set_message, v, self.name)

    @log_on_start(DEBUG, "{self.name:s}: Starting to check termination buses")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while checking termination buses")
    @log_on_end(DEBUG, "{self.name:s}: Finished checking termination buses")
    async def checkTerminationBuses(self):

        # Look at all of the termination buses
        termination_bus_values = await self.collectBusesToValues(self.termination_buses)

        # If any of the termination buses have triggered (gone true or non-negative), signal the loop to end
        for tbv in termination_bus_values:
            if tbv and tbv >= 0:
                return True



class Producer(ConsumerProducer):

    @log_on_start(DEBUG, "{name:s}: Starting to create producer")
    @log_on_error(DEBUG, "{name:s}: Encountered an error while creating producer")
    @log_on_end(DEBUG, "{name:s}: Finished creating producer")
    def __init__(self,
                 producer_function,
                 output_buses,
                 delay=0,
                 termination_buses=Bus(False, "Default producer termination bus"),
                 name="Unnamed producer"):

        # Producers don't use an input bus
        input_buses = Bus(0, "Default producer input bus")

        # Match naming convention for this class with its parent class
        # def syntax is necessary because a producer function will not accept
        # input values
        def consumer_producer_function(_input_value): return producer_function()

        # Call the parent class init function
        super().__init__(
            consumer_producer_function,
            input_buses,
            output_buses,
            delay,
            termination_buses,
            name)


    @log_on_start(DEBUG, "{self.name:s}: Starting consumer-producer service")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while closing down consumer-producer")
    @log_on_end(DEBUG, "{self.name:s}: Closing down consumer-producer service")
    async def __call__(self):

        while True:

            # Check if the loop should terminate
            # termination_value = self.termination_buses[0].get_message(self.name)
            if await self.checkTerminationBuses():
                break

            # Collect all of the values from the input buses into a list
            input_values = await self.collectBusesToValues(self.input_buses)

            # Get the output value or tuple of values corresponding to the inputs
            output_values = self.consumer_producer_function(*input_values)

            # Deal the values into the output buses
            await self.dealValuesToBuses(output_values, self.output_buses)

            # Pause for set amount of time
            await asyncio.sleep(self.delay)


class Consumer(ConsumerProducer):

    @log_on_start(DEBUG, "{name:s}: Starting to create consumer")
    @log_on_error(DEBUG, "{name:s}: Encountered an error while creating consumer")
    @log_on_end(DEBUG, "{name:s}: Finished creating consumer")
    def __init__(self,
                 consumer_function,
                 input_buses,
                 delay=0,
                 termination_buses=Bus(False, "Default consumer termination bus"),
                 name="Unnamed consumer"):

        # Match naming convention for this class with its parent class
        consumer_producer_function = consumer_function

        # Consumers don't use an output bus
        output_buses = Bus(0, "Default consumer output bus")

        # Call the parent class init function
        super().__init__(
            consumer_producer_function,
            input_buses,
            output_buses,
            delay,
            termination_buses,
            name)


    @log_on_start(DEBUG, "{self.name:s}: Starting consumer-producer service")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while closing down consumer-producer")
    @log_on_end(DEBUG, "{self.name:s}: Closing down consumer-producer service")
    async def __call__(self):

        while True:

            # Check if the loop should terminate
            # termination_value = self.termination_buses[0].get_message(self.name)
            if await self.checkTerminationBuses():
                break

            # Collect all of the values from the input buses into a list
            input_values = await self.collectBusesToValues(self.input_buses)

            # Get the output value or tuple of values corresponding to the inputs
            output_values = self.consumer_producer_function(*input_values)

            # Deal the values into the output buses
            await self.dealValuesToBuses(output_values, self.output_buses)

            # Pause for set amount of time
            await asyncio.sleep(self.delay)


class Printer(Consumer):

    @log_on_start(DEBUG, "{name:s}: Starting to create printer")
    @log_on_error(DEBUG, "{name:s}: Encountered an error while creating printer")
    @log_on_end(DEBUG, "{name:s}: Finished creating printer")
    def __init__(self,
                 printer_bus,  # bus or tuple of buses that should be printed to the terminal
                 delay=0,  # how many seconds to sleep for between printing data
                 termination_buses=Bus(False, "Default printer termination bus"),  # buses to check for termination
                 name="Unnamed termination timer",  # name of this printer
                 print_prefix="Unspecified printer: "):  # prefix for output

        super().__init__(
            self.print_bus,  # Printer class defines its own printing function
            printer_bus,
            delay,
            termination_buses,
            name)

        self.print_prefix = print_prefix

    @log_on_start(DEBUG, "{self.name:s}: Starting consumer-producer service")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while closing down consumer-producer")
    @log_on_end(DEBUG, "{self.name:s}: Closing down consumer-producer service")
    async def __call__(self):

        while True:

            # Check if the loop should terminate
            # termination_value = self.termination_buses[0].get_message(self.name)
            if await self.checkTerminationBuses():
                break

            # Collect all of the values from the input buses into a list
            input_values = await self.collectBusesToValues(self.input_buses)

            # Get the output value or tuple of values corresponding to the inputs
            output_values = self.consumer_producer_function(*input_values)

            # Deal the values into the output buses
            await self.dealValuesToBuses(output_values, self.output_buses)

            # Pause for set amount of time
            await asyncio.sleep(self.delay)

    def print_bus(self, *messages):
        output_string = self.print_prefix                  # Start the output string with the print prefix
        for msg in messages:                               # Append bus messages to the output

            if msg is None:
                msg_str = "None"
            elif isinstance(msg, str):                       # If the message is a string, leave it as it is
                msg_str = msg
            else:                                          # If it's not a string, assume it's a number and convert it
                msg_str = str("{0:.4g}".format(msg))       # Convert to string with 4 significant figures
                if msg >= 0:                               # Append a space before the value if it is not negative
                    msg_str = " " + msg_str

            output_string = output_string + " " + msg_str  # Append the message string to the output string

            for i in range(1, 12 - len(msg_str)):          # Add spacing to put the outputs into columns
                output_string = output_string + " "

        print(output_string)                               # Print the formatted output

class Timer(Producer):

    @log_on_start(DEBUG, "{name:s}: Starting to create timer")
    @log_on_error(DEBUG, "{name:s}: Encountered an error while creating timer")
    @log_on_end(DEBUG, "{name:s}: Finished creating timer")
    def __init__(self,
                 output_buses,  # buses that receive the countdown value
                 duration=5,  # how many seconds the timer should run for (0 is forever)
                 delay=0,  # how many seconds to sleep for between checking time
                 termination_buses=Bus(False, "Default timer termination bus"),
                 name="Unnamed termination timer"):

        super().__init__(
            self.timer,  # Timer class defines its own producer function
            output_buses,
            delay,
            termination_buses,
            name)

        self.duration = duration
        self.t_start = time.time()

    @log_on_start(DEBUG, "{self.name:s}: Starting consumer-producer service")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while closing down consumer-producer")
    @log_on_end(DEBUG, "{self.name:s}: Closing down consumer-producer service")
    async def __call__(self):

        while True:

            # Check if the loop should terminate
            # termination_value = self.termination_buses[0].get_message(self.name)
            if await self.checkTerminationBuses():
                break

            # Collect all of the values from the input buses into a list
            input_values = await self.collectBusesToValues(self.input_buses)

            # Get the output value or tuple of values corresponding to the inputs
            output_values = self.consumer_producer_function(*input_values)

            # Deal the values into the output buses
            await self.dealValuesToBuses(output_values, self.output_buses)

            # Pause for set amount of time
            await asyncio.sleep(self.delay)

    @log_on_start(DEBUG, "{self.name:s}: Checking current time against starting time")
    @log_on_error(DEBUG, "{self.name:s}: Encountered an error while checking current time against starting time")
    @log_on_end(DEBUG, "{self.name:s}: Finished checking current time against starting time")
    def timer(self):

        # Trigger the timer if the duration is non-zero and the time elapsed
        # since instantiation is longer than the duration
        if self.duration:
            time_relative_to_end_time = time.time() - self.t_start - self.duration
            return time_relative_to_end_time
        else:
            return False

"""
Third change: Replace the runConcurrently function with a version that calls asyncio.run. This function requires
a helper function (gather) to set up the execution calls
"""

@log_on_start(DEBUG, "runConcurrently: Starting concurrent execution")
@log_on_error(DEBUG, "runConcurrently: Encountered an error during concurrent execution")
@log_on_end(DEBUG, "runConcurrently: Finished concurrent execution")
async def gather(producer_consumer_list):
    """
    Function that uses asyncio.gather to concurrently
    execute a set of ConsumerProducer functions
    """

    # Make a new list of producer_consumers by evaluating the input list
    # (this evaluation matches syntax with rossros.py)
    producer_consumer_list2 = []
    for pc in producer_consumer_list:
        producer_consumer_list2.append(pc())

    await asyncio.gather(*producer_consumer_list2)


def runConcurrently(producer_consumer_list):
    """
    Function that uses asyncio.run to tell asyncio.gather to run a list of
    ConsumerProducers
    """
    asyncio.run(gather(producer_consumer_list))
