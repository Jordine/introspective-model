"""
Wait for 10-epoch training to finish, then launch all evals.
Run: nohup python -u scripts/auto_launch_10epoch_evals.py > logs/auto_launch_10epoch.log 2>&1 &
"""
import subprocess
import time
import os

CHECKPOINT_DIR = '/root/project/checkpoints/original_10epoch'
LOG_FILE = '/root/project/logs/original_10epoch.log'
PROJECT_DIR = '/root/project'

def training_done():
    """Check if training has finished by looking for 'best' and 'final' dirs."""
    best = os.path.exists(os.path.join(CHECKPOINT_DIR, 'final', 'adapter_model.safetensors'))
    return best

def launch_evals():
    os.chdir(PROJECT_DIR)
    
    evals = [
        # GPU 0: Detection
        f'CUDA_VISIBLE_DEVICES=0 nohup python -u scripts/evaluate.py --adapter checkpoints/original_10epoch/best --output-dir results/v3/detection/original_10epoch --vectors vectors/random_vectors.pt > logs/eval_detection_10epoch.log 2>&1 &',
        # GPU 2: Logprobs
        f'CUDA_VISIBLE_DEVICES=2 nohup python -u scripts/eval_logprobs_expanded.py --adapter_path checkpoints/original_10epoch/best --output_dir results/v3/logprobs/original_10epoch > logs/eval_logprobs_10epoch.log 2>&1 &',
        # GPU 3: Self-prediction
        f'CUDA_VISIBLE_DEVICES=3 nohup python -u scripts/eval_self_prediction.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct --adapter_path checkpoints/original_10epoch/best --output_dir results/v3/self_prediction/original_10epoch > logs/eval_selfpred_10epoch.log 2>&1 &',
        # GPU 5: Self-calibration
        f'CUDA_VISIBLE_DEVICES=5 nohup python -u scripts/eval_self_calibration.py --adapter_path checkpoints/original_10epoch/best --output_dir results/v3/self_calibration/original_10epoch > logs/eval_selfcalib_10epoch.log 2>&1 &',
        # GPU 6: Token prediction
        f'CUDA_VISIBLE_DEVICES=6 nohup python -u scripts/eval_token_prediction.py --model_name Qwen/Qwen2.5-Coder-32B-Instruct --adapter_path checkpoints/original_10epoch/best --output_dir results/v3/token_prediction/original_10epoch > logs/eval_tokenpred_10epoch.log 2>&1 &',
    ]
    
    print(f'Launching {len(evals)} evals...')
    for cmd in evals:
        print(f'  {cmd[:80]}...')
        subprocess.Popen(cmd, shell=True, cwd=PROJECT_DIR)
        time.sleep(2)  # Stagger launches
    print('All evals launched!')

if __name__ == '__main__':
    print('Waiting for 10-epoch training to complete...')
    print(f'Checking for: {CHECKPOINT_DIR}/final/adapter_model.safetensors')
    
    while not training_done():
        # Check training log for progress
        try:
            result = subprocess.run(['tail', '-1', LOG_FILE], capture_output=True, text=True)
            last_line = result.stdout.strip()[-200:] if result.stdout else 'no output'
            print(f'[{time.strftime("%H:%M:%S")}] Still training... {last_line}')
        except:
            print(f'[{time.strftime("%H:%M:%S")}] Still waiting...')
        time.sleep(60)  # Check every minute
    
    print(f'\n[{time.strftime("%H:%M:%S")}] Training complete! Launching evals...')
    time.sleep(10)  # Wait a bit for files to settle
    launch_evals()
    print('Done! Monitor eval logs in /root/project/logs/')
