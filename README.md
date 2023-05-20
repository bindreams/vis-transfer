# Visual file transfer scripts
This repository is a proof-of-concept method of transferring files in and out of secure systems and networks by displaying them as a series of QR codes, which can then be recorded and decoded on another computer.

`send.py` script will prompt you to choose a single file and then immediately display a series of QR codes. Record them,
then use the recording file as a first argument in `recv.py`, with the second argument being the path to save the decoded file.

## License
The project is licensed under the GNU GPL version 3 only.
