# Sandbox image for artifact generation (Phase 9 + Phase 10).
#
# Why a dedicated image instead of pip-installing at runtime: the sandbox runs
# with default-deny egress, so a `pip install python-pptx` inside it fails by
# design. Every library a generator needs must therefore be baked in here.
# The alternative - opening egress to PyPI for "just the sandbox" - would
# defeat the sovereignty requirement in the one container that executes
# model-authored code.
#
# This image is referenced by purpose, not by name, from the model's point of
# view: `SandboxPolicy.resolve_image("documents")`. Nothing in a tool schema
# accepts an image reference, so an LLM cannot ask for a different one.
#
# Build (on the deployment machine, where PyPI is reachable):
#
#   docker build -f infrastructure/docker/sandbox-documents.Dockerfile \
#     -t project117/sandbox-documents:1.0 .
#
# Then pin it by digest, so a re-tagged image cannot silently change what runs:
#
#   docker image inspect project117/sandbox-documents:1.0 \
#     --format '{{index .RepoDigests 0}}'
#
# and set in .env:
#
#   P117_SANDBOX_DOCUMENTS_IMAGE=project117/sandbox-documents:1.0
#   P117_SANDBOX_DOCUMENTS_IMAGE_DIGEST=sha256:...
#
# Versions are pinned exactly. An unpinned generator dependency means the
# artifact checker can pass today and fail next month for reasons nobody
# changed.

FROM python:3.11-slim

# No build toolchain is installed: every wheel below is available prebuilt for
# this platform, and a compiler in an image that runs untrusted code is extra
# attack surface for nothing.
RUN pip install --no-cache-dir \
      python-pptx==1.0.2 \
      python-docx==1.1.2 \
      openpyxl==3.1.5 \
      reportlab==4.2.5 \
      pandas==2.2.3 \
      matplotlib==3.9.2

# Workspace layout the generators and SandboxPolicy agree on:
#   /workspace/inputs    - spec.json and any uploaded data (read)
#   /workspace/artifacts - the produced file (write, size-capped)
#   /workspace/tmp       - scratch
RUN mkdir -p /workspace/artifacts /workspace/inputs /workspace/tmp

# Never root. A container escape starting as uid 0 is a materially worse day
# than one starting as uid 10001.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox \
    && chown -R 10001:10001 /workspace

# Mirrors SandboxPolicy.environment() so behaviour is the same whether the
# variable arrives from the policy or from the image.
ENV HOME=/workspace \
    TMPDIR=/workspace/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1 \
    MPLBACKEND=Agg

WORKDIR /workspace
USER 10001

# OpenSandbox supplies the entrypoint when it creates the sandbox; this is a
# harmless default for `docker run` smoke tests.
CMD ["python3", "-c", "import pptx, docx, openpyxl, reportlab; print('documents image ok')"]
