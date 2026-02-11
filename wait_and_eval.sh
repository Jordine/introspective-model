#\!/bin/bash
# Wait for all training to finish, then kick off evals
cd /root/project

echo "$(date): Waiting for training to complete..."

while true; do
    # Check if any python finetune.py processes are still running
    if \! pgrep -f "finetune.py" > /dev/null 2>&1; then
        echo "$(date): All training processes finished\!"
        break
    fi
    
    # Print status
    running=$(pgrep -f "finetune.py" -c 2>/dev/null || echo 0)
    echo "$(date): $running training processes still running"
    sleep 120
done

echo ""
echo "=== TRAINING COMPLETE ==="
echo ""

# Print final results from logs
for f in logs/train_*.log; do
    echo "=== $(basename $f) ==="
    grep -E "(Final|Best|val_acc)" "$f" | tail -5
    echo ""
done

# Check for results.json
for d in checkpoints/*/; do
    name=$(basename $d)
    if [ -f "$d/results.json" ]; then
        echo "=== $name results.json ==="
        cat "$d/results.json"
        echo ""
    fi
done

echo ""
echo "$(date): Starting evaluation suite..."
echo ""

# Download original model adapter from HF
if [ \! -d "checkpoints/original/best" ]; then
    echo "Downloading original adapter from HuggingFace..."
    python -c "
from huggingface_hub import snapshot_download
snapshot_download(Jordine/qwen2.5-coder-32b-introspection-r16, local_dir=checkpoints/original/best)
print(Done)
"
fi

# Install lm-eval if needed
pip install lm-eval 2>/dev/null

# Run the eval suite
bash scripts/run_v2_evals.sh 0

echo ""
echo "$(date): ALL EVALS COMPLETE"
