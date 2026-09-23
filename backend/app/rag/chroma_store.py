"""骨架占位文件：只声明职责与契约，尚无实现。

 - 向量层，本地 ./data/chroma。
   只有 topic_definitions / fallacy_examples / walton_schemes 三个 jsonl 进 Chroma；
   predicate_vocab、source_tiers、safety_patterns 是精确匹配表，
   **不进 Chroma**——词表一旦 embed 化就退化成已废弃的相似度判定。
 - ORCHID 中文辩论语料不入表：现有指标没有一项消费它，且其标注能否作真值无出处；
   若日后要建标准正反论点库，必须先解决它的授权问题。
"""
