## 抖音/TikTok/快手视频去水印

> 本项目作为[`wechat-gptbot`](https://github.com/iuiaoin/wechat-gptbot)插件，可以去除抖音/TikTok/快手等视频的水印。

### 安装

添加以下配置到插件源配置文件`plugins/source.json`:
```yaml
  "douyin_scraper": {
    "repo": "https://github.com/al-one/wechat-douyin-scraper.git",
    "desc": "抖音/TikTok/快手视频去水印"
  }
```

### 配置

添加以下配置到配置文件`config.json`:
```yaml
  "plugins": [
    {
      "name": "douyin_scraper",
      "command": ["复制打开抖音", "v.douyin", "tiktok.com", "kuaishou.com"],
      "with_link": true, # 同时发送链接
      "only_link": true  # 仅发送链接
    }
  ]
```

### 鸣谢

- https://github.com/Evil0ctal/Douyin_TikTok_Download_API
