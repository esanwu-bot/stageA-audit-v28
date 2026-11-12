# v1 ↔ v2 Parser 输出对照（证明修复影响面）

- v1 = `runs/gate6a_replay_v1/per_sample`（格线修复**前**，V256 崩溃）
- v2 = `runs/gate6a_replay_v2_postfix/per_sample`（格线修复**后**，V256 复活）
- 比对文件：`text_blocks.json`、`tables.json`、`candidates.json`、`boundary_decisions.json`、`product.json`
- 双口径：**文件口径**逐字节 sha256；**结构口径**剔除时间戳/run_id 后规范化 sha256

## 1. 结论

- 其余 23 件：结构口径 **69/69 一致**，业务内容零变化。
- 其余 23 件：文件口径不一致 0 处（逐字节完全相同）。
- V256：v1 无任何 Parser 产物（第 57 页崩溃），v2 产出 5 个文件，属「新增」而非「修改」。
- 因此修复的**影响面被严格限制在 V256 一件**，满足「除 V256 外输出不变」的硬边界。

## 2. 逐件逐文件明细

| 样本 | 文件 | 文件口径 | 结构口径 | v1 sha256 | v2 sha256 |
| --- | --- | --- | --- | --- | --- |
| V003 | `text_blocks.json` | 一致 | ✅ | `71587e3e5548` | `71587e3e5548` |
| V003 | `tables.json` | 一致 | ✅ | `2817d8654d79` | `2817d8654d79` |
| V003 | `candidates.json` | 一致 | ✅ | `e28f359422ce` | `e28f359422ce` |
| V003 | `boundary_decisions.json` | 一致 | （不适用） | `1f6510fc1f08` | `1f6510fc1f08` |
| V003 | `product.json` | 一致 | （不适用） | `9b496d074ef9` | `9b496d074ef9` |
| V011 | `text_blocks.json` | 一致 | ✅ | `4eb0ff7f7197` | `4eb0ff7f7197` |
| V011 | `tables.json` | 一致 | ✅ | `432c820e8a85` | `432c820e8a85` |
| V011 | `candidates.json` | 一致 | ✅ | `800e7853395c` | `800e7853395c` |
| V011 | `boundary_decisions.json` | 一致 | （不适用） | `11dfa1e395e2` | `11dfa1e395e2` |
| V011 | `product.json` | 一致 | （不适用） | `bff788c03a01` | `bff788c03a01` |
| V038 | `text_blocks.json` | 一致 | ✅ | `51226f749fef` | `51226f749fef` |
| V038 | `tables.json` | 一致 | ✅ | `986953f37e14` | `986953f37e14` |
| V038 | `candidates.json` | 一致 | ✅ | `711154b7da6f` | `711154b7da6f` |
| V038 | `boundary_decisions.json` | 一致 | （不适用） | `5ac1697a9019` | `5ac1697a9019` |
| V038 | `product.json` | 一致 | （不适用） | `1b055530829c` | `1b055530829c` |
| V077 | `text_blocks.json` | 一致 | ✅ | `18f3c536848d` | `18f3c536848d` |
| V077 | `tables.json` | 一致 | ✅ | `6fbd714bdb99` | `6fbd714bdb99` |
| V077 | `candidates.json` | 一致 | ✅ | `b69844f74478` | `b69844f74478` |
| V077 | `boundary_decisions.json` | 一致 | （不适用） | `4ac22c1cb287` | `4ac22c1cb287` |
| V077 | `product.json` | 一致 | （不适用） | `95c30a39b883` | `95c30a39b883` |
| V097 | `text_blocks.json` | 一致 | ✅ | `aadceabec578` | `aadceabec578` |
| V097 | `tables.json` | 一致 | ✅ | `5dd66312a891` | `5dd66312a891` |
| V097 | `candidates.json` | 一致 | ✅ | `00b28d52da49` | `00b28d52da49` |
| V097 | `boundary_decisions.json` | 一致 | （不适用） | `c1b7da9a7583` | `c1b7da9a7583` |
| V097 | `product.json` | 一致 | （不适用） | `3995f054f0d8` | `3995f054f0d8` |
| V101 | `text_blocks.json` | 一致 | ✅ | `cd03e0108f8b` | `cd03e0108f8b` |
| V101 | `tables.json` | 一致 | ✅ | `8460c39e2365` | `8460c39e2365` |
| V101 | `candidates.json` | 一致 | ✅ | `3dd79124cdbd` | `3dd79124cdbd` |
| V101 | `boundary_decisions.json` | 一致 | （不适用） | `ef9e7ed434bb` | `ef9e7ed434bb` |
| V101 | `product.json` | 一致 | （不适用） | `946f16bdc40a` | `946f16bdc40a` |
| V111 | `text_blocks.json` | 一致 | ✅ | `13a8f7e062ec` | `13a8f7e062ec` |
| V111 | `tables.json` | 一致 | ✅ | `a72de795765f` | `a72de795765f` |
| V111 | `candidates.json` | 一致 | ✅ | `4fe116146b0f` | `4fe116146b0f` |
| V111 | `boundary_decisions.json` | 一致 | （不适用） | `f2b8fa168455` | `f2b8fa168455` |
| V111 | `product.json` | 一致 | （不适用） | `c719cc292a92` | `c719cc292a92` |
| V145 | `text_blocks.json` | 一致 | ✅ | `b447b727ab48` | `b447b727ab48` |
| V145 | `tables.json` | 一致 | ✅ | `aafd2b1a2c5c` | `aafd2b1a2c5c` |
| V145 | `candidates.json` | 一致 | ✅ | `58907b71e5bc` | `58907b71e5bc` |
| V145 | `boundary_decisions.json` | 一致 | （不适用） | `557d26e02750` | `557d26e02750` |
| V145 | `product.json` | 一致 | （不适用） | `ba8507bf60a3` | `ba8507bf60a3` |
| V146 | `text_blocks.json` | 一致 | ✅ | `8d93712c1841` | `8d93712c1841` |
| V146 | `tables.json` | 一致 | ✅ | `76eb2500b268` | `76eb2500b268` |
| V146 | `candidates.json` | 一致 | ✅ | `d121baa96ddf` | `d121baa96ddf` |
| V146 | `boundary_decisions.json` | 一致 | （不适用） | `270c046f6112` | `270c046f6112` |
| V146 | `product.json` | 一致 | （不适用） | `531e10fd1dca` | `531e10fd1dca` |
| V162 | `text_blocks.json` | 一致 | ✅ | `039e4fac6f3f` | `039e4fac6f3f` |
| V162 | `tables.json` | 一致 | ✅ | `3d3fda0546a9` | `3d3fda0546a9` |
| V162 | `candidates.json` | 一致 | ✅ | `741bef3a48f4` | `741bef3a48f4` |
| V162 | `boundary_decisions.json` | 一致 | （不适用） | `8501913f9334` | `8501913f9334` |
| V162 | `product.json` | 一致 | （不适用） | `ad7ccbe030c0` | `ad7ccbe030c0` |
| V173 | `text_blocks.json` | 一致 | ✅ | `c48de67138d4` | `c48de67138d4` |
| V173 | `tables.json` | 一致 | ✅ | `28d7f53ac3e3` | `28d7f53ac3e3` |
| V173 | `candidates.json` | 一致 | ✅ | `4f413cf9076f` | `4f413cf9076f` |
| V173 | `boundary_decisions.json` | 一致 | （不适用） | `2bab1ad8d9a9` | `2bab1ad8d9a9` |
| V173 | `product.json` | 一致 | （不适用） | `4858afa23c87` | `4858afa23c87` |
| V199 | `text_blocks.json` | 一致 | ✅ | `b96ac5eb1990` | `b96ac5eb1990` |
| V199 | `tables.json` | 一致 | ✅ | `3e399423abd3` | `3e399423abd3` |
| V199 | `candidates.json` | 一致 | ✅ | `058769986cc9` | `058769986cc9` |
| V199 | `boundary_decisions.json` | 一致 | （不适用） | `b420c3773d16` | `b420c3773d16` |
| V199 | `product.json` | 一致 | （不适用） | `7513af2d83fc` | `7513af2d83fc` |
| V242 | `text_blocks.json` | 一致 | ✅ | `464c0ed872a3` | `464c0ed872a3` |
| V242 | `tables.json` | 一致 | ✅ | `232dcae487f5` | `232dcae487f5` |
| V242 | `candidates.json` | 一致 | ✅ | `437464ac11f3` | `437464ac11f3` |
| V242 | `boundary_decisions.json` | 一致 | （不适用） | `367b187c76f2` | `367b187c76f2` |
| V242 | `product.json` | 一致 | （不适用） | `b5a603bd0369` | `b5a603bd0369` |
| V244 | `text_blocks.json` | 一致 | ✅ | `2bc5722ad4c9` | `2bc5722ad4c9` |
| V244 | `tables.json` | 一致 | ✅ | `62e9108278c3` | `62e9108278c3` |
| V244 | `candidates.json` | 一致 | ✅ | `635fd314316e` | `635fd314316e` |
| V244 | `boundary_decisions.json` | 一致 | （不适用） | `ba0b0144efb0` | `ba0b0144efb0` |
| V244 | `product.json` | 一致 | （不适用） | `3f175b77de39` | `3f175b77de39` |
| V256 | `text_blocks.json` | 新增 | 新增 | `-` | `071d94edbdc2` |
| V256 | `tables.json` | 新增 | 新增 | `-` | `8a53643e41f0` |
| V256 | `candidates.json` | 新增 | 新增 | `-` | `9b232c5820d0` |
| V256 | `boundary_decisions.json` | 新增 | 新增 | `-` | `2208a55c47dd` |
| V256 | `product.json` | 新增 | 新增 | `-` | `4cf62f2d3a67` |
| V271 | `text_blocks.json` | 一致 | ✅ | `f6ab236b982c` | `f6ab236b982c` |
| V271 | `tables.json` | 一致 | ✅ | `96e0e424d0c6` | `96e0e424d0c6` |
| V271 | `candidates.json` | 一致 | ✅ | `bdafa23b9e9f` | `bdafa23b9e9f` |
| V271 | `boundary_decisions.json` | 一致 | （不适用） | `996635d98f52` | `996635d98f52` |
| V271 | `product.json` | 一致 | （不适用） | `f0de45ff887e` | `f0de45ff887e` |
| V290 | `text_blocks.json` | 一致 | ✅ | `1ebb047cea65` | `1ebb047cea65` |
| V290 | `tables.json` | 一致 | ✅ | `1db95eebcf38` | `1db95eebcf38` |
| V290 | `candidates.json` | 一致 | ✅ | `f9d2284a830c` | `f9d2284a830c` |
| V290 | `boundary_decisions.json` | 一致 | （不适用） | `45ea4d7c2de9` | `45ea4d7c2de9` |
| V290 | `product.json` | 一致 | （不适用） | `b78b9a22ba5f` | `b78b9a22ba5f` |
| V304 | `text_blocks.json` | 一致 | ✅ | `55c8db467274` | `55c8db467274` |
| V304 | `tables.json` | 一致 | ✅ | `73b05003c6c9` | `73b05003c6c9` |
| V304 | `candidates.json` | 一致 | ✅ | `f20c22c10947` | `f20c22c10947` |
| V304 | `boundary_decisions.json` | 一致 | （不适用） | `f54360572103` | `f54360572103` |
| V304 | `product.json` | 一致 | （不适用） | `4c19e498122a` | `4c19e498122a` |
| V319 | `text_blocks.json` | 一致 | ✅ | `8684ea03a271` | `8684ea03a271` |
| V319 | `tables.json` | 一致 | ✅ | `075a3ec392c9` | `075a3ec392c9` |
| V319 | `candidates.json` | 一致 | ✅ | `434b9bad8bf5` | `434b9bad8bf5` |
| V319 | `boundary_decisions.json` | 一致 | （不适用） | `790a63352270` | `790a63352270` |
| V319 | `product.json` | 一致 | （不适用） | `5560b2b88e1b` | `5560b2b88e1b` |
| V320 | `text_blocks.json` | 一致 | ✅ | `3607243ec452` | `3607243ec452` |
| V320 | `tables.json` | 一致 | ✅ | `5b6e6cf5b22d` | `5b6e6cf5b22d` |
| V320 | `candidates.json` | 一致 | ✅ | `e08c4fe1f80c` | `e08c4fe1f80c` |
| V320 | `boundary_decisions.json` | 一致 | （不适用） | `e5e844d50857` | `e5e844d50857` |
| V320 | `product.json` | 一致 | （不适用） | `c74638e92699` | `c74638e92699` |
| V336 | `text_blocks.json` | 一致 | ✅ | `b1f50be85f95` | `b1f50be85f95` |
| V336 | `tables.json` | 一致 | ✅ | `6e2792017f1d` | `6e2792017f1d` |
| V336 | `candidates.json` | 一致 | ✅ | `fadbcd32e39c` | `fadbcd32e39c` |
| V336 | `boundary_decisions.json` | 一致 | （不适用） | `c7445b08c6e7` | `c7445b08c6e7` |
| V336 | `product.json` | 一致 | （不适用） | `5a58cef8f89a` | `5a58cef8f89a` |
| V345 | `text_blocks.json` | 一致 | ✅ | `262c460ff4bc` | `262c460ff4bc` |
| V345 | `tables.json` | 一致 | ✅ | `73ef75e10098` | `73ef75e10098` |
| V345 | `candidates.json` | 一致 | ✅ | `4b8bef835939` | `4b8bef835939` |
| V345 | `boundary_decisions.json` | 一致 | （不适用） | `f126a999a1f8` | `f126a999a1f8` |
| V345 | `product.json` | 一致 | （不适用） | `62d81acd2a47` | `62d81acd2a47` |
| V346 | `text_blocks.json` | 一致 | ✅ | `165bbbc58e4c` | `165bbbc58e4c` |
| V346 | `tables.json` | 一致 | ✅ | `dd3318fefd5e` | `dd3318fefd5e` |
| V346 | `candidates.json` | 一致 | ✅ | `e75ecdcec2f9` | `e75ecdcec2f9` |
| V346 | `boundary_decisions.json` | 一致 | （不适用） | `41e57a021896` | `41e57a021896` |
| V346 | `product.json` | 一致 | （不适用） | `28d688d6e8eb` | `28d688d6e8eb` |
| V349 | `text_blocks.json` | 一致 | ✅ | `a9c2dd8562b1` | `a9c2dd8562b1` |
| V349 | `tables.json` | 一致 | ✅ | `d3532f59c43e` | `d3532f59c43e` |
| V349 | `candidates.json` | 一致 | ✅ | `4c7cd9a4198b` | `4c7cd9a4198b` |
| V349 | `boundary_decisions.json` | 一致 | （不适用） | `157d2e3a5735` | `157d2e3a5735` |
| V349 | `product.json` | 一致 | （不适用） | `1a3f26095072` | `1a3f26095072` |

## 3. 规模对照（表数 / 行数）

| 样本 | v1 tables.json | v2 tables.json | 一致 |
| --- | --- | --- | --- |
| V003 | 364 表 / 4525 行 | 364 表 / 4525 行 | 是 |
| V011 | 20 表 / 298 行 | 20 表 / 298 行 | 是 |
| V038 | 199 表 / 1549 行 | 199 表 / 1549 行 | 是 |
| V077 | 215 表 / 3316 行 | 215 表 / 3316 行 | 是 |
| V097 | 22 表 / 277 行 | 22 表 / 277 行 | 是 |
| V101 | 14 表 / 195 行 | 14 表 / 195 行 | 是 |
| V111 | 33 表 / 404 行 | 33 表 / 404 行 | 是 |
| V145 | 92 表 / 806 行 | 92 表 / 806 行 | 是 |
| V146 | 14 表 / 104 行 | 14 表 / 104 行 | 是 |
| V162 | 31 表 / 415 行 | 31 表 / 415 行 | 是 |
| V173 | 18 表 / 156 行 | 18 表 / 156 行 | 是 |
| V199 | 11 表 / 92 行 | 11 表 / 92 行 | 是 |
| V242 | 356 表 / 2525 行 | 356 表 / 2525 行 | 是 |
| V244 | 189 表 / 3098 行 | 189 表 / 3098 行 | 是 |
| V256 | 0 表 / 0 行 | 337 表 / 2543 行 | 否 |
| V271 | 359 表 / 6099 行 | 359 表 / 6099 行 | 是 |
| V290 | 6 表 / 45 行 | 6 表 / 45 行 | 是 |
| V304 | 18 表 / 164 行 | 18 表 / 164 行 | 是 |
| V319 | 12 表 / 89 行 | 12 表 / 89 行 | 是 |
| V320 | 101 表 / 947 行 | 101 表 / 947 行 | 是 |
| V336 | 11 表 / 107 行 | 11 表 / 107 行 | 是 |
| V345 | 77 表 / 660 行 | 77 表 / 660 行 | 是 |
| V346 | 124 表 / 1052 行 | 124 表 / 1052 行 | 是 |
| V349 | 78 表 / 640 行 | 78 表 / 640 行 | 是 |

## 4. 为什么 V256 必须变

V256 第 57 页是双栏版式被识别成一个 `text_alignment` 区域，
右侧跨行单元格使行带 top/bottom 交错，`(prev_bottom + cur_top)/2`
产出倒序格线（`543.035 → 533.715` 等 3 处），触发 `DetectedTable` 校验崩溃。
修复后 3 处边界被夹紧到「前一位 + 0.2pt」，仍保持原有行序，单元格 26 个
且 `(text, row, column)` 序列完全不变。详见 `v256_crash_evidence.md`。

这正是「不排序、只夹紧」的设计目的：如果改成排序，行索引会整体错位，
V256 会产出看起来正常但内容错乱的表——那才是真正的证据丢失。
