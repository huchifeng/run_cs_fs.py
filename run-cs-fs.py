# 实现了多文件的编译选项分析,合并
# 去掉了 option 函数名, exec 改成 eval
import os
import re
import subprocess
import sys
import shutil
import threading
import time 


re_python = r'[(/]\*#!python(.*?)\*[/)]'
re_cs_fs=r'(.*)\.(cs|fs)$'
output = r'd:\run_fx' 
if not os.path.exists(output): os.mkdir(output)

def get_main_dir(): # 如果应用程序是被打包的，
    return os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)else os.path.dirname(os.path.abspath(__file__))
print('get_main_dir', get_main_dir()) # pytest 下也是脚本目录
os.chdir(get_main_dir())
print('os.getcwd', os.getcwd())  

'''
['OutputType', 'WinExe'],
['--reference:', 'System.Text.Json.dll'],   /r:
['/unsafe'],
['/platform:x86'],
['xxx.cs'],
['PackageReference', 'log4net', "2.0.13"],
#  Visual Studio 中设置启动对象 <StartupObject/>; csc.exe 本身不支持直接通过命令行参数指定启动对象。
['main', ''], # 执行代码
'''

syslib = [r'C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.7.2',
          r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\WPF']
default_dll = ['PresentationFramework.dll','WindowsBase.dll','WindowsFormsIntegration.dll', 'PresentationCore.dll', 'PresentationFramework.dll', 'System.Xaml.dll']

def open_read(f):
    try: return open(f, encoding='utf-8-sig').read() # 无BOM不会报错; 反之 utf-8 会把 BOM 作为字符 65279
    except Exception as ex: return open(f, encoding='gbk').read()

def parse_options_from_src(all_cs): 
    options_in_src = []
    i = 0
    main_code = []
    while i< len(all_cs):
        cs = all_cs[i]
        i+= 1
        print('parse', cs)
        src = open_read(cs)
        for m in re.findall(re_python, src, flags=re.DOTALL):
            print(m)
            options = eval(m) # 可以考虑 try 异常再 exec
            options_in_src += [opt for opt in options if opt[0]!='main']
            if i==1: #not len(main_code): # 只取第一个
                main_code += [opt for opt in options if opt[0]=='main']
            files = [os.path.abspath(os.path.join(os.path.dirname(cs), i[0])) for i in options if len(i)==1 and (i[0].endswith('.cs')or i[0].endswith('.fs'))]
            all_cs += [f for f in files if  f not in all_cs] # 去重复
    options_in_src = list(set(tuple(s) for s in options_in_src)) # tuple 可 hash, sorted
    options_in_src += main_code
    return options_in_src

def compile_fx(cs, debug, rebuild):  
    exe =  os.path.join(output, re.sub(r'\.(fs|cs)$', '.exe', os.path.basename(cs)))
    print(exe, os.path.exists(exe))
    if not rebuild and os.path.exists(exe) and os.path.getmtime(exe)>os.path.getmtime(cs):
        return exe
    if(os.path.exists(exe)): os.remove(exe)
    all_cs = [os.path.abspath(cs)]
    options_in_src=parse_options_from_src(all_cs)
    if cs.endswith('.cs'):        
        compiler = [r'D:\Tools\roslyn\csc.exe'] + ['/lib:'+d for d in syslib+[output]] + ['/out:'+exe]
    else:
        compiler = [r'D:\Tools\FSharp\Tools\fsc.exe'] +['--lib:'+d for d in syslib+[output]] + ['--define:NETFRAMEWORK', '--out:'+exe]
    # print(options_in_src)
    for i in options_in_src:
        if i[0]=='main':
            f  = os.path.join(output, 'main.cs')
            with open(f, 'w', encoding='utf-8-sig') as fh: 
                # ImplicitUsings
                fh.write('''using System; using System.Collections.Generic; using System.Linq; 
                         using System.Drawing; using System.Windows.Forms; using System.Net; 
                         using System.Text; using System.Text.RegularExpressions;
                         using System.Threading; using System.Threading.Tasks;
                         class Program{static int Main(string[] args){ try{ '''+ i[1]+ '''
                         ; return 0; }
                         catch(Exception ex){ Console.Error.WriteLine(ex.ToString()); return -1;}   }}''')
            all_cs.append(f)
        if i[0].startswith('/r:') or i[0]=='--reference:':
            f  = i[1] if i[0]=='--reference:' else i[0].split(':')[1]
            f1 = os.path.abspath( os.path.join(output, f) ) 
            if os.path.exists(f2) and (not os.path.exists(f1) or os.path.getmtime(f2)>os.path.getmtime(f1)):
                print(f2, '->', f1) # FSharp.Core.dll 之类还是会缺
                shutil.copy(f2, f1)  
    a = compiler + [''.join(i) for i in options_in_src if i[0]=='--reference:' or i[0].startswith('/')  
                    ] + ['/r:'+d for d in default_dll] + all_cs
    print(a)
    if (exitCode:=subprocess.run(a).returncode) != 0:
        print('exit', exitCode)
    bindingRedirect = [a for a in options_in_src if a[0]=='bindingRedirect']
    if(len(bindingRedirect)>0):
        exeConfigFileName = exe+'.config'
        with open(exeConfigFileName, mode='w', encoding='utf-8-sig') as exeConfig:
            exeConfig.write(f'''<?xml version="1.0" encoding="utf-8"?>
<configuration>   
  <runtime>
    <assemblyBinding xmlns="urn:schemas-microsoft-com:asm.v1"> 
      {''.join([f"""<dependentAssembly>
        <assemblyIdentity name="{a[1]}" publicKeyToken="{a[2]}" culture="neutral" />
        <bindingRedirect oldVersion="0.0.0.0-{a[3]}" newVersion="{a[3]}" />
      </dependentAssembly>""" for a in bindingRedirect ])}
    </assemblyBinding>
  </runtime>
</configuration>
 ''')
    return exe 

     
def main(cs, argv):
    print(argv)
    if re.match(re_cs_fs, cs): 
        argv1 = argv[:]
        argv2 = []
        if '/' in argv:
            i = argv.index('/')
            argv1 = argv[:i]
            argv2 = argv[i+1:] # / 之前是编译选项
        exe = compile_fx(cs, '-d' in argv1, '-r' in argv1) 
        if not os.path.exists(exe):
            exit(-1)
        if os.path.exists(exe):
            print('-'*10+' begin '+'-'*10)
            exitcode = subprocess.run([exe]+ argv2).returncode
            print('-'*10+' done '+'-'*10)
            print('exitcode', exitcode)
            if(exitcode!=0): exit(exitcode) # exit 导致 pytest fail
    else: print('??',  argv) 
    
# pytest run-cs-fs.py::test_1 -s 
def test_1(): #  
    main('../../test1.fs', [])

if __name__ == '__main__': 
    try:
        main(sys.argv[1], sys.argv[1:])
    except Exception as ex:
        print('ERROR', ex)
        exit(-1)
    
