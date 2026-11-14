# 🎬 Love Movie — 追影人 & 影视系列追踪助手

IMDb 为主、豆瓣电影辅助的个人追影与追剧看板，专为手机端（GitHub App / 手机浏览器）设计：不用开电脑，在手机上改一下 watchlist.yaml，GitHub Actions 就会自动抓取最新动态并更新到本页。

## 📱 手机端日常怎么用？

1. 添加想追的影人或影视系列：在 GitHub App 或手机浏览器中打开 watchlist.yaml，点右上角编辑，填入影人或影视的 IMDb ID（直接粘贴手机 IMDb App 分享出来的链接也可以，脚本会自动提取 nm 或 tt 编号），保存提交即可。
2. 自动或手动刷新数据：每次修改 watchlist.yaml 后会自动触发抓取；也可以随时点仓库顶部的 Actions -> Update Movie Tracker -> Run workflow 手动刷新（每天北京时间 10:00 也会自动运行一次）。

## 🎬 最新追影看板
尚未运行首次抓取，请前往 Actions -> Update Movie Tracker -> Run workflow 手动触发一次即可生成。
