# run_cs_fs.py

#### 介绍
刚从C++转C#时, 觉得C# 不用include 很方便,

时间长了觉得这是一个设计失误, 类之间随意递归引用是不好的,
F# 严一些, 要求源码按顺序来, 前面的 .fs 不能引用后面的 .fs, 但也不需要明确说明 一个源码文件依赖哪些其他源码;
C# F# 所依赖的库也都是列在项目文件里而不是 代码 里;

感觉 python 的方式比较好, 每个 py 文件都要清楚的列出所 import 的库 或其他 py 文件;

所以写了个 py 程序用来构建 C# F# 程序, 不用 C# F# 的工程文件;
在每个 .cs .fs 文件开头列出所依赖的 dll 和 其他 文件,
例如
``` 
/*#!python
[
    ['common.cs'],
    ['/unsafe'],
    ['/r:log4net.dll'], 
    ['bindingRedirect', 'System.Runtime.CompilerServices.Unsafe', 'b03f5f7f11d50a3a', '6.0.0.0', ], # 设定 app.config 的 bindingRedirect
    ['main', ' Console.WriteLine("hello,world,"+XXX.YYY); '],
]
*/
//对于 fs是 (*#!python  *)
public class XXX
{
   public int YYY=100;
}
```



然后 python 构建程序找出所有依赖, 编译构建
其中的 main 用来对没有  Main 入口的代码 添加 入口,
使得每个 cs 都可以单独运行, 测试功能