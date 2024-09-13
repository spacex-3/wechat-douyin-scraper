import os
from datetime import datetime, timedelta
from scraper import DouyinScraper
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import *
import json


class DouyinScraperPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.limit_size_mb = self.config.get("limit_size_mb", 50)  # 默认50MB
        self.keep_assets_days = self.config.get("keep_assets_days", 3)
        self.scraper = DouyinScraper(self.config.get("cookies", ""))  # 实例化scraper并传入cookies

        # 插件元数据
        self.name = "DouyinScraperPlugin"
        self.description = "A plugin to scrape Douyin videos and download them without watermark."

    def load_config(self):
        """加载插件的配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"{config_path} 配置文件未找到")

    def on_handle_context(self, e_context: EventContext):
        """
        处理微信消息，判断是否为抖音链接并处理
        """
        context = e_context['context']
        if context.type != ContextType.TEXT:
            return  # 只处理文本消息

        message = context.content.strip()

        # 判断消息是否包含抖音相关的关键词
        if "v.douyin.com" in message or "复制打开抖音" in message:
            self.handle_douyin_message(message, e_context)
        else:
            # 如果不是抖音链接，不处理消息
            return

    def handle_douyin_message(self, message, e_context: EventContext):
        """
        处理抖音链接消息
        """
        # 提取抖音链接
        douyin_url = self.extract_douyin_url(message)
        if not douyin_url:
            return

        e_context['reply'].append(Reply(ReplyType.INFO, "正在解析抖音链接，请稍候..."))

        # 调用scraper解析无水印视频地址
        video_data = self.scraper.get_douyin_video_data(douyin_url)
        if not video_data:
            e_context['reply'].append(Reply(ReplyType.ERROR, "无法解析抖音链接，请检查链接是否有效。"))
            return

        # 获取无水印视频URL
        video_url = video_data.get('video_url')
        if not video_url:
            e_context['reply'].append(Reply(ReplyType.ERROR, "未能获取视频链接。"))
            return

        # 下载视频
        video_path = self.download_video(video_url)
        if not video_path:
            e_context['reply'].append(Reply(ReplyType.ERROR, f"视频下载失败，或文件大小超过 {self.limit_size_mb} MB 限制。"))
            return

        # 发送视频
        e_context['reply'].append(Reply(ReplyType.VIDEO, video_path))
        os.remove(video_path)  # 发送后删除临时文件

    def extract_douyin_url(self, message):
        """
        从消息中提取抖音链接
        """
        # 简单的字符串匹配，提取出 v.douyin.com 开头的链接
        start = message.find("v.douyin.com")
        if start != -1:
            end = message.find(" ", start)  # 假设链接以空格结束
            return message[start:end].strip()
        return None

    def download_video(self, video_url):
        """
        下载视频并检查视频大小
        """
        video_path = self.scraper.download_video(video_url, self.limit_size_mb)
        return video_path

    def clean_old_assets(self):
        """
        清理超过 keep_assets_days 天数的视频文件
        """
        temp_dir = '/tmp'
        now = datetime.now()
        cutoff_time = now - timedelta(days=self.keep_assets_days)

        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_time:
                    os.remove(file_path)

    def install(self):
        # 插件安装时的初始化工作
        pass

    def uninstall(self):
        # 插件卸载时的清理工作
        pass


# 插件初始化
def init():
    return DouyinScraperPlugin()
