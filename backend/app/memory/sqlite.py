"""骨架占位文件：只声明职责与契约，尚无实现。

 - SQLAlchemy 2.0 异步 + aiosqlite；库文件在 ./data 下。
   边界要写明：谁能读该目录即拿到全部记忆，本机部署不做租户隔离。
 - 建表含 claims 的谓词列与 contradictions 的 who / type DDL；
   patterns 表留到跨会话记忆真正启用时才建。
"""
