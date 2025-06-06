import asyncio

from src.data_processing.processor import process_data

asyncio.run(process_data("downloads/ff.xlsx", None,
                         None,None,
                         None, "weighted", [1,2,3], None))