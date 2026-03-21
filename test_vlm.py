import asyncio
from src.aimodel.image_processing.vlm import get_vlm_description

async def test_vlm():
    url = "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhRBcAsgnmYVPG0GmEk-rMHRo39hLRjUtAQg_woo_drIjaKwkwMyBHByb2RQgL2jAVoQOwdEjfKBci8gyrI83mno_noCyzKCAQJneg&rkey=CAESMMm7WzbeR52hynLIBedwSO_KzpiZEYADssQahtjSsBG5w1myfb2J89gwQBiRzktZFw"
    print("正在测试 VLM 图片描述...")
    result = await get_vlm_description(url, True)
    print(f"结果: {result}")

if __name__ == "__main__":
    asyncio.run(test_vlm())
