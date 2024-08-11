# Visual File Trasfer: Send
Send files using a GUI on a machine in a secure network.

Requirements:
- [Python](https://www.python.org/downloads/) 3.11 or greater
- Internet access to PyPI from terminal. You can test this by running `pip install numpy`.
  If you can access PyPI from browser (https://pypi.org/) but `pip install` fails with a connection error, you can
  download required dependencies manually (see below).

Clone this repository or download a the "send" folder as a [zip file from GitHub](https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2Fbindreams%2Fvis-transfer%2Ftree%2Fmain%2Fsend) and extract it anywhere. Open a terminal window in the root folder.

If you'd like to have no trace of installation left after you delete the folder, at this point you should create and activate a virtual environment:
```sh
python -m venv .venv
.venv/Scripts/Activate.ps1  # PowerShell on Windows
# source .venv/bin/activate  # POSIX shells
```

Run the following command to install the "send" package. Then run the command open the send GUI and follow the instructions:
```sh
pip install --no-cache-dir --editable send
vis-transfer-send
```
