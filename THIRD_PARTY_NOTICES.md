# Third-party notices

The MIT license in this repository covers this project's original code and documentation. It does not relicense model weights, dependencies, external binaries, or user-supplied source documents.

## Kokoro speech synthesis

- **kokoro-onnx**, by thewh1teagle and contributors: MIT. See the [upstream license](https://github.com/thewh1teagle/kokoro-onnx/blob/main/LICENSE) and [project](https://github.com/thewh1teagle/kokoro-onnx). The optional speech dependency is pinned to version 0.6.1.
- **Kokoro-82M model**, by its upstream authors: Apache License 2.0, as identified in the [official model card](https://huggingface.co/hexgrad/Kokoro-82M) and the [kokoro-onnx license summary](https://github.com/thewh1teagle/kokoro-onnx#license). The model card also contains training-data acknowledgements and attribution information.
- The downloader retrieves `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the upstream [model-files-v1.1 release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1). Neither file is bundled with this repository. Consult the release and original model documentation for the applicable terms before redistributing model or voice assets. Do not assume this repository's MIT license covers them.

## Libraries and external tools

Python packages are installed separately using their upstream distributions. These include markdown-it-py, NumPy, SoundFile, ONNX Runtime, kokoro-onnx, and their transitive dependencies. Their own license and notice files remain authoritative. A source checkout is not a bundled redistribution of those dependencies.

The selected text-to-phoneme route uses [phonemizer](https://github.com/bootphon/phonemizer), licensed GPLv3 or later, and [eSpeak NG](https://github.com/espeak-ng/espeak-ng), licensed GPLv3 or later. [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader) provides access to the native eSpeak NG library; its loader code and bundled native library have their own license files. These copyleft dependencies are not relicensed by this repository. Review their exact distribution terms before packaging an application or container that includes them.

FFmpeg and ffprobe are separately installed tools. [FFmpeg's licensing page](https://ffmpeg.org/legal.html) explains that the base project uses LGPL 2.1 or later, while optional GPL components can change the licensing of a particular build. Check the actual binary's build configuration and licenses before redistributing it. SoundFile may also distribute native libraries under separate terms.

## Redistribution

This file is an attribution guide, not a complete license bundle or legal advice. If you distribute an environment, executable, container, or archive containing third-party code or model assets, include the license texts and notices required for those exact versions, and satisfy any applicable source-code obligations. Retain upstream attribution and clearly identify modifications where required.

Source articles and resulting audio are not automatically licensed under this repository's MIT license. Review rights to the source material and applicable upstream terms before publication.
