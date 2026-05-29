import asyncio
import aiohttp
import time

# الرابط الفعلي لعرض المنتجات في تطبيق الـ catalog بمشروعك
URL = "http://127.0.0.1:8000/api/catalog/" 
NUMBER_OF_REQUESTS = 5

async def send_request(session, req_id):
    print(f"🚀 Request [{req_id}] Sent...")
    async with session.get(URL) as response:
        data = await response.json()
        print(f"📥 Request [{req_id}] Response source: {data.get('source')}")

async def main():
    print(f"🔥 Sending {NUMBER_OF_REQUESTS} concurrent requests to test Redis Caching on Product List...")
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, i) for i in range(1, NUMBER_OF_REQUESTS + 1)]
        await asyncio.gather(*tasks)
    end_time = time.time()
    print(f"\n⏱️ Process finished in: {(end_time - start_time)*1000:.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())