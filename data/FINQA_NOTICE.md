# FinQA sample notice

`finqa_sample.json` contains three adapted examples from the FinQA development
split:

- `V/2008/page_17.pdf-1`
- `C/2017/page_328.pdf-1`
- `DVN/2007/page_58.pdf-2`

The added `qa.exe_ans_scale` field records whether each numerical gold answer
uses an ordinary number, decimal ratio, or percentage-point convention. It is
scorer-only metadata and is never included in the model prompt.

Source: https://github.com/czyssrs/FinQA

FinQA paper:

> Zhiyu Chen et al. “FinQA: A Dataset of Numerical Reasoning over Financial
> Data.” EMNLP 2021.

The examples are reduced to the gold supporting evidence, table, question, and
execution answer needed by this small oracle-context demonstration.

## Upstream license

MIT License

Copyright (c) 2021 Zhiyu Chen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
