import asyncio

from src.data_processing.processor import process_data


asyncio.run(process_data("./downloads/ff.xlsx", 1, None, None, None, division=[4]))