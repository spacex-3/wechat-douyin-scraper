import requests
import re
import execjs  # 用于执行JavaScript代码
import hashlib
import time

class DouyinScraper:
    def __init__(self, cookies):
        self.cookies = cookies
        self.douyin_api_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Cookie": self.cookies,
        }

    def generate_x_bogus(self, url):
        """
        生成 X-Bogus 签名，确保抖音请求合法性
        """
        # 使用 execjs 执行 JavaScript 代码生成 X-Bogus
        # 你需要有一个本地的 X-Bogus 生成函数，通常这是由抖音的加密机制生成的。
        with open("x_bogus.js") as f:
            js_code = f.read()
        ctx = execjs.compile(js_code)
        x_bogus = ctx.call("generateXBogus", url)
        return x_bogus

    def get_douyin_video_data(self, douyin_url):
        """
        获取抖音视频的详细数据，包括无水印视频URL
        """
        # 转换短链接为长链接，获取视频ID
        long_url = self.get_long_url(douyin_url)
        video_id = self.extract_video_id(long_url)

        # 构造抖音API的请求URL
        video_api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"

        # 生成X-Bogus签名并追加到URL
        x_bogus = self.generate_x_bogus(video_api_url)
        final_url = f"{video_api_url}&X-Bogus={x_bogus}"

        # 请求抖音API获取视频数据
        response = requests.get(final_url, headers=self.douyin_api_headers)
        if response.status_code != 200:
            return None

        video_data = response.json()
        if video_data.get("item_list"):
            video_url = video_data["item_list"][0]["video"]["play_addr"]["url_list"][0]
            return {
                "video_url": video_url
            }
        return None

    def get_long_url(self, short_url):
        """
        转换抖音的短链接为长链接
        """
        response = requests.head(short_url, allow_redirects=True)
        return response.url

    def extract_video_id(self, long_url):
        """
        从长链接中提取视频ID
        """
        match = re.search(r'/video/(\d+)', long_url)
        if match:
            return match.group(1)
        return None

    def download_video(self, video_url, limit_size_mb):
        """
        下载视频，并检查文件大小是否超过限制
        """
        try:
            response = requests.get(video_url, stream=True, timeout=30)
            total_size = int(response.headers.get('content-length', 0))

            # 将大小限制转为字节，并检查是否超过限制
            limit_size_bytes = limit_size_mb * 1024 * 1024
            if total_size > limit_size_bytes:
                print(f"文件大小 {total_size} 超过限制 {limit_size_bytes}")
                return None

            video_path = os.path.join('/tmp', 'douyin_video.mp4')  # 保存到临时目录
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            return video_path
        except Exception as e:
            print(f"下载视频时发生错误: {e}")
            return None
