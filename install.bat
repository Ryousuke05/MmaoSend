@echo off
chcp 65001 > nul
title 一键安装环境

echo 检查 Python 是否存在...

python --version > nul 2>&1

if %errorlevel% == 0 (
    echo 已检测到 Python，跳过安装
    goto INSTALL_DEPS
)

echo.
echo 未检测到 Python，开始下载 3.10.9...

set PY_INSTALLER=python-3.10.9-amd64.exe
set DOWNLOAD_URL=https://mirrors.tuna.tsinghua.edu.cn/python/3.10.9/python-3.10.9-amd64.exe

if not exist %PY_INSTALLER% (
    echo 正在下载 %PY_INSTALLER%...
    curl -L %DOWNLOAD_URL% -o %PY_INSTALLER%
)

if not exist %PY_INSTALLER% (
    echo 下载失败，请检查网络连接： %DOWNLOAD_URL%
    pause
    exit
)

echo 正在静默安装 Python...

%PY_INSTALLER% /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

echo 安装完成，重新加载环境变量...

call refreshenv > nul 2>&1

python --version > nul 2>&1

if %errorlevel% neq 0 (
    echo Python 安装失败，请手动检查
    pause
    exit
)


echo.
echo 安装依赖...

python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

if %errorlevel% neq 0 (
    echo 依赖安装失败
    pause
    exit
)

pause