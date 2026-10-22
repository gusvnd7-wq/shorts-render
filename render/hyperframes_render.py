# Kaggle 에서 템톡 HyperFrames 화면 렌더 — 여러 회차를 한 번에 (2026-10-20, char-reel/kaggle/run.py 와 같은 설치 순서)
#   입력: 데이터셋 robbin0707/temtalk-render-bundle 의 bundle.tar (job.json + 프로젝트 폴더들, PC에서 index.html·assets 까지 만든 것)
#   출력: /kaggle/working/<프로젝트>.mp4 + result.json. 소리 섞기·검수는 PC(tools/temtalk/render.mjs).
import subprocess, os, glob, json, time, shutil
W = "/kaggle/working"; RES = {"ok": False, "items": {}}; T0 = time.time()
HFV = "0.7.109"; NODEV = "v22.11.0"
# REMOTE-ROTATE(10/22): GitHub·Blacksmith 서버는 root가 아니라 apt-get에 sudo가 필요하고 /root에 못 씀 → 권한·캐시 경로를 서버에 맞춤(Kaggle은 root라 그대로)
SUDO = "" if os.geteuid() == 0 else "sudo "; PCACHE = os.path.expanduser("~/.cache/puppeteer")
def sh(c, t=5400, env=None):
    print("$", c, flush=True); t0 = time.time()
    r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t, env=env); out = r.stdout + r.stderr
    print(out[-2500:], flush=True); return r.returncode, out, round(time.time() - t0, 1)
def done():
    RES["total_min"] = round((time.time() - T0) / 60, 1); json.dump(RES, open(W + "/result.json", "w"), indent=1); print(RES, flush=True)
try:
    P = "/tmp/p"; os.makedirs(P, exist_ok=True)
    tar = glob.glob("/kaggle/input/**/bundle.tar", recursive=True)
    if tar: sh(f"tar -xf '{tar[0]}' -C {P}")
    else:
        job0 = glob.glob("/kaggle/input/**/job.json", recursive=True)[0]; sh(f"cp -r '{os.path.dirname(job0)}'/. {P}/")
    job = json.load(open(P + "/job.json")); RES["job"] = job
    PKGS = "ffmpeg fontconfig fonts-noto-cjk fonts-noto-color-emoji libgbm1 libnss3 libnspr4 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libatk1.0-0 libatk1.0-0t64 libatk-bridge2.0-0 libatk-bridge2.0-0t64 libatspi2.0-0 libatspi2.0-0t64 libcups2 libcups2t64 libasound2 libasound2t64 libgtk-3-0 libgtk-3-0t64"
    sh(SUDO + "apt-get update -qq > /dev/null 2>&1; for p in " + PKGS + "; do DEBIAN_FRONTEND=noninteractive " + SUDO + "apt-get install -y -qq --no-install-recommends $p > /dev/null 2>&1 || echo 없음:$p; done; fc-cache -f > /dev/null", 1800)
    sh(f"cd /tmp && wget -q https://nodejs.org/dist/{NODEV}/node-{NODEV}-linux-x64.tar.xz && tar xf node-{NODEV}-linux-x64.tar.xz", 600)
    ENV = dict(os.environ, PATH=f"/tmp/node-{NODEV}-linux-x64/bin:" + os.environ["PATH"], CONTAINER="true", PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="true")
    sh("npx --yes @puppeteer/browsers install chrome-headless-shell@stable --path " + PCACHE, 900, ENV)
    shell = ([p for p in glob.glob(PCACHE + "/**/chrome-headless-shell", recursive=True) if os.path.isfile(p) and os.access(p, os.X_OK)] or [""])[0]
    ENV["PRODUCER_HEADLESS_SHELL_PATH"] = shell; RES["shell"] = shell
    sh(f"npm install -g hyperframes@{HFV}", 900, ENV)
    # INPAINT(10/20): assets/clips/c<i>.mask.png(흰 상자 = 자막 자리)가 있는 컷은 ProPainter 영상 인페인팅으로 자막을 지운다(흐림 가림 대신)
    masks = sorted(glob.glob(f"{P}/*/assets/clips/*.mask.png"))
    RES["inpaint"] = {"n": len(masks), "ok": 0, "fail": []}
    if masks:
        sh("cd /tmp && git clone -q --depth 1 https://github.com/sczhou/ProPainter.git && cd ProPainter && pip install -q av addict einops future scipy scikit-image imageio-ffmpeg pyyaml timm yapf > /dev/null 2>&1", 1200)
        import cv2
        for mk in masks:
            clip = mk.replace(".mask.png", ".mp4"); nm = os.path.basename(clip)[:-4] + "_" + os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(clip))))
            cap = cv2.VideoCapture(clip); w = int(cap.get(3)); h = int(cap.get(4)); fps = cap.get(5) or job["fps"]; cap.release()
            ratio = 1.0 if max(w, h) <= 700 else (0.5 if max(w, h) <= 1400 else 0.34)   # 고화질은 줄여 지운 뒤 키워서 그 자리만 덮는다(GPU 메모리)
            os.makedirs(f"/tmp/pp/{nm}/{nm}", exist_ok=True); sh(f"ffmpeg -v error -y -i '{clip}' -q:v 2 /tmp/pp/{nm}/{nm}/%05d.jpg")   # 최신 torchvision엔 read_video가 없어 프레임 폴더로(10/20)
            rc, out, sec = sh(f"cd /tmp/ProPainter && PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python inference_propainter.py --video /tmp/pp/{nm}/{nm} --mask {mk} --output /tmp/pp/out --fp16 --save_fps {round(fps)} --resize_ratio {ratio} --mask_dilation 10 --subvideo_length 40 --neighbor_length 10 --ref_stride 10", 1800)
            res = f"/tmp/pp/out/{nm}/inpaint_out.mp4"
            if rc != 0 or not os.path.exists(res): RES["inpaint"]["fail"].append([nm, out[-400:]]); continue
            # 자막 자리(마스크, 살짝 번지게)만 지운 화면으로, 나머지는 원본 그대로
            crf = 34 if job["quality"] == "draft" else 15
            rc2, o2, _ = sh(f"ffmpeg -v error -y -i '{clip}' -i {res} -loop 1 -i '{mk}' -filter_complex \"[1:v]scale={w}:{h}:flags=lanczos,fps={fps},format=rgba[ip0];[2:v]scale={w}:{h},format=gray,gblur=sigma=1.5[m];[ip0][m]alphamerge[ip];[0:v][ip]overlay=0:0:shortest=1,format=yuv420p[v]\" -map '[v]' -shortest -c:v libx264 -preset {'ultrafast' if crf == 34 else 'slow'} -crf {crf} /tmp/pp/{nm}.fixed.mp4 && mv /tmp/pp/{nm}.fixed.mp4 '{clip}'", 900)
            if rc2 == 0: RES["inpaint"]["ok"] += 1
            else: RES["inpaint"]["fail"].append([nm, "merge " + o2[-300:]])
    for name in job["projects"]:
        rc, out, sec = sh(f"cd '{P}/{name}' && hyperframes render --output '{W}/{name}.mp4' --fps {job['fps']} --quality {job['quality']} --crf {job['crf']}", 5400, ENV)
        ok = rc == 0 and os.path.exists(f"{W}/{name}.mp4")
        RES["items"][name] = {"ok": ok, "render_s": sec, "tail": "" if ok else out[-1200:]}
    RES["ok"] = all(v["ok"] for v in RES["items"].values())
except Exception as e:
    RES["error"] = repr(e)
done()
