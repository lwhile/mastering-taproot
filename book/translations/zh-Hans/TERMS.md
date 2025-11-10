# TERMS.md — Bitcoin Script / Taproot 术语映射表（zh-Hans）

> 本表用于保证中英文术语一致性。中文优先保持“技术直观 + 不破坏概念语义”，必要时保留英文。

| English term | 中文建议 | 说明 |
|---|---|---|
| internal key | 内部公钥 | Taproot 镜像根，key path 的起点 |
| x-only public key | x-only 公钥 | BIP340 公钥只有 X 坐标 |
| tweak | tweak（不翻） | 不翻最稳，中文翻“改调/调谐”会污染语义 |
| key tweaking | key tweaking | 本质是 tweakable commitment，不翻 |
| control block | control block（控制块） | script-path reveal 的结构头部 |
| script path spend | script-path 支出 | P2TR 的脚本路径 |
| key path spend | key-path 支出 | P2TR 直接用 tweaked key |
| annex | annex（BIP342） | 推荐不翻 |
| merkle root | merkle 根 | |
| leaf version | leaf版本号 | |
| witness program | witness 程序 | |
| BIP340 / BIP341 / BIP342 | 不翻 | 直接用 BIP 编号 |
| signature parity bit | 奇偶标记 | control block 低 1 bit |
| even-y | even-y | 不翻更技术准确 |
| non-malleable | 不可篡改 / 不可修改 | 文中 prefer “不可篡改” |
| spendscript / witnessScript | 见证脚本 | |
| commitment | 承诺 | taproot 语境“可验证前向承诺” |
| tap tweak | tap tweak（不翻） | BIP341 专名，不建议翻 |
| Schnorr signature | Schnorr 签名 | |
| signature uniqueness | 签名唯一性 | 替代你原来的 “signature aggregation” |
