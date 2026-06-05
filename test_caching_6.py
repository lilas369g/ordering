import asyncio
import aiohttp
import time

URL = "http://127.0.0.1:8000/api/v1/catalog/products/"
NUMBER_OF_REQUESTS = 5

async def send_request(session, req_id):
    print(f"🚀 Request [{req_id}] Sent...")
    start = time.time()
    async with session.get(URL) as response:
        data = await response.json()
        elapsed = (time.time() - start) * 1000
        source = data.get('source', 'database')  # default = database
        count = len(data) if isinstance(data, list) else len(data.get('results', []))
        print(f"📥 Request [{req_id}] — {elapsed:.0f}ms — source: {source} — products: {count}")

async def main():
    print(f"🔥 Sending {NUMBER_OF_REQUESTS} concurrent requests...")
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, i) for i in range(1, NUMBER_OF_REQUESTS + 1)]
        await asyncio.gather(*tasks)
    end_time = time.time()
    print(f"\n⏱️ Total: {(end_time - start_time)*1000:.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())