# Docker Hub 部署说明

## 方法一：使用 GitHub Actions（推荐）

1. 在 GitHub 仓库中设置 Secrets：
   - 进入仓库的 Settings > Secrets and variables > Actions
   - 添加以下 Secrets：
     - `DOCKER_USERNAME`: 你的 Docker Hub 用户名（getyourhub）
     - `DOCKER_PASSWORD`: 你的 Docker Hub 密码或访问令牌

2. 推送代码到 main 分支，GitHub Actions 会自动构建并推送镜像到 Docker Hub

3. 镜像地址：`getyourhub/abogen-bilingual:latest`

## 方法二：本地构建并推送

1. 确保已登录 Docker Hub：
   ```bash
   docker login --username getyourhub
   ```

2. 运行构建脚本：
   ```bash
   ./build_and_push.sh
   ```

## 使用镜像

拉取镜像：
```bash
docker pull getyourhub/abogen-bilingual:latest
```

运行容器：
```bash
docker run -p 8808:8808 -v ./data:/data getyourhub/abogen-bilingual:latest
```

访问 Web UI：http://localhost:8808