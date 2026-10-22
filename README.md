# shorts-render
세로 쇼츠(1080×1920) 렌더 일꾼. [HyperFrames](https://www.npmjs.com/package/hyperframes)로 HTML 장면을 MP4로 렌더한다.

- `render/hyperframes_render.py`: 렌더 일꾼 본체. 입력 묶음(`job.json` + 프로젝트 폴더들)을 받아 ffmpeg·크롬 헤드리스·HyperFrames를 설치하고 프로젝트마다 MP4를 만든다. 자막 자리 마스크가 있으면 ProPainter로 지운다(GPU가 있을 때).
- `.github/workflows/remote.yml`: 손으로 부를 때만 도는 렌더 실행 틀(`workflow_dispatch`). 결과 MP4는 실행 결과물(artifact)로 2일 보관.
- 입력 묶음과 비밀값은 이 저장소에 없다(실행 때 받아 옴).
