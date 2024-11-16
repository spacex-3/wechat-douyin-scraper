import os
import re
import json
import requests
import plugins
import time
from datetime import datetime, timedelta
from common.log import logger
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from pathlib import Path
from plugins import *
from config import conf
from pathvalidate import sanitize_filename

@plugins.register(
    name="DouyinPlugin",
    desire_priority=90,
    hidden=False,
    desc="一款基于douyin API获取去水印视频的插件。",
    version="1.0",
    author="SpaceX",
)

class DouyinPlugin(Plugin):
    def __init__(self):
        super().__init__()
        try:# 配置文件路径
            curdir = os.path.dirname(__file__)
            self.config_path = os.path.join(curdir, "config.json")
            # 加载配置文件
            self.config = self.load_config()
            self.api_base_url = f"{self.config['api_base_url'].rstrip('/')}/api/hybrid/video_data"
            self.assets_dir = Path(curdir) / 'douyin_assets'  # 存储临时文件的路径
            self.assets_dir.mkdir(exist_ok=True)  # 创建文件夹
            logger.debug(f"Assets directory created at: {self.assets_dir}")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_RECEIVE_MESSAGE] = self.on_receive_message

        except Exception as e:
            logger.error(f"[DouyinPlugin] init failed, ignored.")
            raise e

    def load_config(self):
        """
        加载配置文件，初始化 limit_size 和 keep_assets_days
        """
        if not os.path.exists(self.config_path):
            default_config = {
                "api_base_url": "",
                "limit_size": 50,  # 视频大小限制，单位MB
                "keep_assets_days": 3  # 文件保留天数
            }
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f)
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def save_config(self):
        """
        保存配置文件
        """
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)

    def is_douyin_link(self, text):
        """
        检查文本中是否包含抖音链接，只要包含douyin.com就触发
        """
        douyin_pattern = r'douyin\.com'
        return re.search(douyin_pattern, text)

    def get_douyin_video_data(self, douyin_url, retries=3, wait_time=5):
        """
        调用抖音API，获取无水印视频数据，包含重试机制
        retries: 最大重试次数
        wait_time: 每次重试的等待时间（秒）
        """
        for attempt in range(retries):
            try:
                response = requests.get(self.api_base_url, params={"url": douyin_url})
                if response.status_code == 200:
                    return response.json().get('data', {})
                else:
                    logger.debug(f"API 请求失败，状态码：{response.status_code}")
            except Exception as e:
                logger.debug(f"API 请求出错: {e}")
            
            # 如果请求失败，等待指定的时间后重试
            logger.debug(f"请求失败，等待 {wait_time} 秒后重试...（第 {attempt + 1} 次重试）")
            time.sleep(wait_time)
        
        # 所有重试都失败，返回 None
        logger.debug("所有重试都失败，无法获取抖音视频数据")
        return None

    def download_video(self, e_context, video_url, file_path, video_size, retry_count=5):
        """
        下载视频并确保大小不超过配置的限制
        """
        # 检查文件大小是否超过限制
        channel = e_context["channel"]
        video_size_mb = round(video_size / (1024 * 1024))  # 保留0位小数，四舍五入
        if video_size_mb > self.config['limit_size']:
            logger.debug(f"视频大小 {video_size_mb}MB 超出限制 {self.config['limit_size']}MB")
            reply = Reply(ReplyType.TEXT, f"视频大小 {video_size_mb}MB 超出限制 {self.config['limit_size']}MB")            
            _send(channel, reply, e_context["context"])
            e_context.action = EventAction.BREAK_PASS

        # 下载视频
        while retry_count >= 0:
            try:
                # 下载视频并发送
                response = requests.get(video_url, allow_redirects=True, stream=True, timeout=200)
                if response.status_code != 200:
                    raise Exception(f"[douyin] 文件下载失败， status_code={response.status_code}")
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)

            except Exception as e:
                logger.debug(f"下载视频出错: {e}")
                retry_count -= 1
                time.sleep(5)

            else:
                # reply = Reply(ReplyType.TEXT, f"下载视频出错。")            
                # _send(channel, reply, e_context["context"])
                # e_context.action = EventAction.BREAK_PASS
                break
        else:
            # 重试次数用尽，发送失败信息
            reply = Reply(ReplyType.TEXT, "下载视频出错。请稍后重试")            
            _send(channel, reply, e_context["context"])
            e_context.action = EventAction.BREAK_PASS

    def cleanup_assets(self):
        """
        清理目录中的视频，仅保留最新的3个视频文件
        """
        # 获取所有 mp4 文件并按修改时间排序
        mp4_files = sorted(self.assets_dir.glob('*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True)

        # 保留最新的3个视频文件，删除其余的
        for file in mp4_files[3:]:
            file.unlink()  # 删除文件
            logger.debug(f"删除多余文件: {file}")



    def on_handle_context(self, e_context: EventContext):
        """
        处理微信消息
        """
        # 判断是否是TEXT类型消息
        if e_context["context"].type not in [ContextType.TEXT]:
            return
        context = e_context["context"]
        text = context.content

        # 判断是否包含抖音链接
        douyin_match = self.is_douyin_link(text)
        if douyin_match:
            e_context.action = EventAction.BREAK_PASS
        else:
            return
        
    def shorten_link(self, long_url):
        """
        调用短链接API将长链接转为短链接
        """
        shorten_api_url = "https://d.zpika.com/api"  # 你的短链接API URL
        payload = {"url": long_url}

        try:
            # 发送请求到短链接API
            response = requests.post(shorten_api_url, json=payload)
            if response.status_code == 200:
                result = response.json()
                # 检查 status 是否为 200，获取短链接路径
                if result.get("status") == 200:
                    return result.get("key")  # 返回短链接路径部分
                else:
                    logger.error(f"Failed to shorten the URL, status code: {result.get('status')}")
                    return None
            else:
                logger.error(f"Failed to shorten the URL: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error while shortening URL: {str(e)}")
            return None

    def on_receive_message(self, e_context: EventContext):
        """
        处理微信消息
        """
        # 判断是否是TEXT类型消息
        if e_context["context"].type not in [ContextType.TEXT]:
            return
        context = e_context["context"]
        channel = e_context["channel"]
        text = context.content

        # 判断是否包含抖音链接
        douyin_match = self.is_douyin_link(text)
        if douyin_match:
            # 直接使用完整的消息文本作为API的参数
            douyin_url = text

            # 调用API获取无水印视频数据
            video_data = self.get_douyin_video_data(douyin_url)
            logger.debug(f"Get video data")

            if video_data:
                # 提取无水印视频链接和视频大小
                # 处理 bit_rate 列表，确保它存在且有元素
                bit_rate_list = video_data.get('video', {}).get('bit_rate', [])
                
                if bit_rate_list and isinstance(bit_rate_list, list):
                    # 从列表中获取第一个元素
                    play_addr = bit_rate_list[0].get('play_addr', {}).get('url_list', [])
                else:
                    play_addr = []

                video_link = play_addr[0] if play_addr else None

                # 获取视频大小，使用 bit_rate 的第一个元素
                video_size = bit_rate_list[0].get('play_addr', {}).get('data_size', 0) if bit_rate_list else 0
                video_size_mb = round(video_size / (1024 * 1024))  # 保留0位小数，四舍五入

                nickname = video_data.get('author', {}).get('nickname', '未知用户')
                desc = video_data.get('desc', '无描述')
                create_time = datetime.fromtimestamp(video_data.get('create_time', 0)).strftime('%Y-%m-%d')

                statistics = video_data.get('statistics', {})
                digg_count = statistics.get('digg_count', 0)
                comment_count = statistics.get('comment_count', 0)
                collect_count = statistics.get('collect_count', 0)
                share_count = statistics.get('share_count', 0)
                
                
                # 下载链接处理
                url_pattern = r'https?://(?:www\.)?douyin\.com/[^\s]+|https?://v\.douyin\.com/[^\s]+'
                short_match = re.search(url_pattern, text)
                douyin_short_url = short_match.group(0)
                download_link = f"{self.config['api_base_url'].rstrip('/')}/api/download?url={douyin_short_url}&prefix=true&with_watermark=false"
                logger.debug(f"[douyin] 下载视频，video_url={download_link}")

                if video_link:
                    #清理过期文件
                    self.cleanup_assets()

                    # 转换视频链接为短链接
                    short_video_link = self.shorten_link(video_link)
                    if short_video_link:
                        # 拼接完整的短链接
                        short_video_link = f"https://d.zpika.com{short_video_link}"
                    else:
                        short_video_link = video_link  # 如果短链接失败，仍然使用长链接

                    # 发送视频信息和观看链接
                    reply = Reply(ReplyType.TEXT, f"抖音视频信息：\n用户: {nickname}, 发布时间: {create_time}, 视频大小: {video_size_mb}MB\n点赞: {digg_count}, 评论: {comment_count}, 收藏: {collect_count}, 分享: {share_count}\n描述: {desc}\n无压缩无水印视频链接：{short_video_link}")
                    channel = e_context["channel"]
                    _send(channel, reply, e_context["context"])

                    # 下载视频
                    filename = f"{int(time.time())}-{sanitize_filename(desc).replace(' ', '')[:20]}"
                    video_path = os.path.join(self.assets_dir, f"{filename}.mp4")
                    self.download_video(e_context, download_link, video_path, video_size)

                    # 发送视频
                    reply = Reply(ReplyType.VIDEO, video_path)
                    _send(channel, reply, e_context["context"])

                    e_context.action = EventAction.BREAK_PASS

                else:
                    reply = Reply(ReplyType.TEXT, "抱歉！没有找到视频链接，请稍后重试。")
                    e_context["reply"] = reply
                    e_context.action = EventAction.BREAK_PASS
            else:
                reply = Reply(ReplyType.TEXT, "抱歉！没有视频信息，请检查视频是否被删除。")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        else:
            return

def _send(channel, reply: Reply, context, retry_cnt=0):
    try:
        channel.send(reply, context)
    except Exception as e:
        logger.error("[WX] sendMsg error: {}".format(str(e)))
        if isinstance(e, NotImplementedError):
            return
        logger.exception(e)
        if retry_cnt < 2:
            time.sleep(3 + 3 * retry_cnt)
            channel.send(reply, context, retry_cnt + 1)
