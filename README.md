# arty-mc

![Python](https://img.shields.io/badge/python-3+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-linux-lightgrey.svg)
![Status](https://img.shields.io/badge/status-experimental-orange.svg)

```text
         o                      o                            o          o             
        <|>                    <|>                          <|\        /|>            
        / \                    < >                          / \\o    o// \            
      o/   \o       \o__ __o    |       o      o            \o/ v\  /v \o/      __o__ 
     <|__ __|>       |     |>   o__/_  <|>    <|>  _\__o__   |   <\/>   |      />  \  
     /       \      / \   < >   |      < >    < >       \   / \        / \   o/       
   o/         \o    \o/         |       \o    o/            \o/        \o/  <|        
  /v           v\    |          o        v\  /v              |          |    \\       
 />             <\  / \         <\__      <\/>              / \        / \    _\o__</ 
                                           /                                          
                                          o                                           
                                       __/>                                           

```

**arty-mc** is a terminal file manager for JFrog Artifactory.

It provides a **dual-pane interface similar to Midnight Commander**, allowing you to **browse, filter, copy and delete** files and folders between **the local filesystem and Artifactory repositories** directly from the terminal.

It uses **Textual** for the terminal interface and **dohq-artifactory** for interacting with Artifactory repositories.

---

# Why arty-mc?

Managing artifacts in Artifactory is often done through the web UI, generic tools like `curl` or the `jf-cli`.
For developers who prefer working directly in the terminal, this can be inconvenient.

---

# Features

* Dual-pane terminal interface
* Browse/Filer local filesystem and Artifactory repositories
* Copy files between panes
* Delete artifacts
* Simple YAML configuration

---

# Screenshot
![arty-mc_screenshot](/media/arty-mc1.png)

---

# Requirements

* Python **3+**
* Access to an **Artifactory server**
* Artifactory **API token**

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/arty-mc.git
cd arty-mc
```

---

## 2. Create a Python Virtual Environment

```bash
mkdir .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. Create Configuration File

Create a configuration file in your home directory:

```text
~/.arty-mc.yml
```

Example configuration:

```yaml
server: https://artifactory.company.com/artifactory
user: myuser
token: ********************************************
```

### Configuration Fields

| Field  | Description                        |
| ------ | ---------------------------------- |
| server | Base URL of the Artifactory server |
| user   | Artifactory username               |
| token  | Artifactory API token              |

---

# Running arty-mc

Run the tool directly:

```bash
python arty-mc.py <repository>
```

Example:

```bash
python arty-mc.py libs-release-local
```

This starts the **dual-pane interface** where you can browse your local filesystem and the selected repository.

---

# Typical Workflow

1. Start **arty-mc** with a repository
2. Navigate the **local filesystem** in one pane
3. Browse the **Artifactory repository** in the other pane
4. Copy files between panes
5. Delete artifacts if needed

⚠ **Warning:** Deleting artifacts from repositories may be irreversible.

---

# Keyboard Shortcuts

| Key   | Action           |
| ----- | ---------------- |
| ↑ ↓   | Navigate         |
| Enter | Open directory   |
| Tab   | Switch pane      |
| F2    | Cancel Operation |
| F5    | Copy             |
| F8    | Delete           |
| F10   | Quit             |

---

# Building an Executable with Pyinstaller

You can build a binary using **PyInstaller**.

Install PyInstaller:

```bash
pip install pyinstaller
```

Build the binary:

**-—onefile:** slower startup caused by runtime extraction

```bash
pyinstaller --onefile --distpath dist --name arty-mc arty-mc.py
```
**-—onedir:** faster after initial startup

```bash
pyinstaller --onedir --distpath dist --name arty-mc arty-mc.py
```

The compiled executable will appear in:

```text
dist/arty-mc/
```

You can run it without a Python environment.

---

# Security Notes

* Do **not** commit your `.arty-mc.yml` file
* Protect your **API token**
* Prefer **API tokens instead of passwords**

---

# Demo

[![Demo Cast](https://asciinema.org/a/wjutM4fkY9r3n05n.svg)](https://asciinema.org/a/wjutM4fkY9r3n05n)

---

# Disclaimer

This software is provided **"as is" without warranty of any kind**.

The tool may contain **bugs or incomplete functionality** and should be used **at your own risk**.
The author assumes **no responsibility or liability for any damage, data loss, system malfunction, or unintended modifications** caused by the use of this software.

Always verify actions such as **uploading, deleting, or overwriting artifacts**, especially when working with production repositories.

This project is **not affiliated with or endorsed by JFrog**.

JFrog and Artifactory are trademarks of JFrog Ltd.

---

# License

MIT License

