# Visual File Trasfer: Receive
Vis-transfer receiver is an executable written in C++23 and compiled with modern CMake 3.25+. It depends upon the following libraries:
- [OpenCV](https://github.com/opencv/opencv), for reading videofiles;
- [ZXing](https://github.com/zxing-cpp/zxing-cpp), for decoding QR codes;
- [LLFIO](https://github.com/ned14/llfio), for memory-mapped files;
- [CryptoPP](https://github.com/weidai11/cryptopp), for hashing.

These libraries can either be installed manually, or using a C++ package manager. This project recommends using [vcpkg](https://github.com/microsoft/vcpkg) on Windows.

From here, building the executable is as simple as running:
```
cmake --preset default
cmake --build build --config Release
cmake --install build --prefix dist --config Release 
```

To decode a previously recorded video file, specify it as a command-line parameter:
```
dist/vis-recv.exe recording.mp4 -o myfile.pdf
```
