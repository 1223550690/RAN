# Join the Collaboration

1. Clone the code to your local machine
Create a new folder with an all-English path, right-click to open Git Bash or a terminal, and execute the clone command:

```bash
# Download the complete code from the cloud to your local machine
git clone [https://github.com/1223550690/RAN.git](https://github.com/1223550690/RAN.git)

# After cloning is complete, you must enter this project directory to perform subsequent operations!
cd RAN
```

2. Configure Local Environment
```
python -m venv .venv 
source .venv/Scripts/activate  # Activate the virtual environment on Windows 
pip install -r requirements.txt
```

3. Token Authentication
Go to your GitHub account: **Settings -> Developer settings -> Personal access tokens (classic)** and generate a Token with the `repo` scope checked. When prompted for a password during a push, choose the Token method and paste this Token.

# Workflow

1. Update the local main branch

```
git switch main
git pull origin main
```

2. Create and switch to a personal branch

```
git switch -c branch_name/task_name
```

3. Commit, push, and submit a PR on the webpage

```
git add .
git commit -m "comment"
git push -u origin branch_name/task_name
```