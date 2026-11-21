**Access Console / SSH:**1 min.

Open SSH or local console to your pfSense box and drop into the FreeBSD root shell (Option `8` from the console menu).

### Step 1: Install Ookla Speedtest CLI via FreeBSD Shell

The official Ookla FreeBSD binary is required to execute native speed tests from the pfSense host.


To install a Speedtest widget on your pfSense dashboard, you typically need to ==install the backend Speedtest CLI package and download the widget's PHP file to your firewall's web directory==. [1]

Depending on whether you want to use the updated Official Ookla Speedtest CLI (recommended for modern versions like pfSense 2.7+ / Plus 24.03+) or the older Python-based Speedtest CLI, you can execute the commands via SSH or under Diagnostics > Command Prompt in the pfSense web interface. [1, 2, 3, 4, 5]

---

## Option 1: Official Ookla CLI Widget (Recommended)

This version by [LeonStraathof](https://github.com/LeonStraathof/pfsense-speedtest-widget) connects to the official Ookla servers for more accurate results. [3, 6]

### 1. Install the official Speedtest CLI package:

```bash
env ABI=FreeBSD:13:x86:64 pkg add "https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-freebsd13-x86_64.pkg"
```

### 2. Accept the licenses (run these sequentially):

```bash
speedtest --accept-license
speedtest --accept-gdpr
```

### 3. Download and install the widget file:

```bash
curl -o /usr/local/www/widgets/widgets/speedtest.widget.php https://raw.githubusercontent.com/aln-1/pfsense-speedtest-widget/master/speedtest.widget.php
```

_(Note: If the repository main branch doesn't feature an `install.sh`, you can place the PHP file directly using the command above)._ [4, 5]

---
## Option 2: Direct Binary Installation

Download and extract the static x86_64 FreeBSD binary directly from Ookla's distribution server:

```shell
pkg install -y pkgconf
cd /tmp
fetch https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-freebsd12-x86_64.pkg
pkg install -y /tmp/ookla-speedtest-1.2.0-freebsd12-x86_64.pkg
rehash
which speedtest
pkg info -l speedtest
```

_If installing the `.pkg` fails due to FreeBSD version matching on pfSense 2.7+/2.8+/2.9+, pull the raw tarball and extract the binary directly:_

```shell
cd /tmp
fetch https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-freebsd12-x86_64.tgz
tar -xzf ookla-speedtest-1.2.0-freebsd12-x86_64.tgz
mv speedtest /usr/local/bin/
chmod +x /usr/local/bin/speedtest
```

**3.Accept License Agreement:**5 secs.

Execute `speedtest` once manually to accept the end-user license agreement:

```Bash
speedtest --accept-license --accept-gdpr
```

- **Verification:** Run `speedtest` in the shell. It should locate a local server, execute the test, and display latency, download, and upload speeds directly in the terminal.

**4. Download and install the widget file:**5 secs.

```bash
pkg update
pkg install -y speedtest-go
curl -o /usr/local/www/widgets/widgets/speedtest.widget.php https://raw.githubusercontent.com/aln-1/pfsense-speedtest-widget/master/speedtest.widget.php
```

---
## Option 3: Unofficial Go-based Widget

If you are tracking the legacy repository by [aln-1](https://github.com/aln-1/pfsense-speedtest-widget), you can install the python dependency and pull the widget in a single combined command: [5, 7]

```bash
pkg update
pkg install -y speedtest-go
#pkg install -y py311-speedtest-cli
curl -o /usr/local/www/widgets/widgets/speedtest.widget.php https://raw.githubusercontent.com/aln-1/pfsense-speedtest-widget/master/speedtest.widget.php
```

_(Adjust `py311` to match your current system python version if necessary)._ [8]

---
## Next Steps: Activating the Widget

1. Log in to your pfSense web dashboard.
2. Click the Available Widgets (plus `+` icon) in the top-right corner of the dashboard screen.
3. Select Speedtest from the dropdown list to add it to your panel. [1, 4, 7]

⚠️ _Note: Running regular speed tests directly on a firewall is resource-heavy and can artificially inflate CPU utilization, which may briefly impact your routing performance._ [9]

### Configure Widget Settings

Click the wrench icon on the new Speedtest widget to set your test schedule (e.g., cron interval) and preferred server ID.

- **Verification:** Click the **Run Test** button on the newly added dashboard widget. It should display your current WAN speed, ping, and jitter directly on your dashboard.

## ==System Upgrade Note==

==Custom widget files installed via raw shell scripts under /usr/local/www/widgets/ are stored on the pfSense system drive. When upgrading pfSense System OS versions in the future, you may need to re-run the install.sh script to restore the widget UI files.==



[1] [https://forum.netgate.com](https://forum.netgate.com/topic/184090/speed-test-panel-under-pfsense-2-7-0-free-bsd14)

[2] [https://www.reddit.com](https://www.reddit.com/r/PFSENSE/comments/1crn4sz/installing_ookla_speedtest_on_modern_supported/)

[3] [https://forum.netgate.com](https://forum.netgate.com/topic/185363/new-widget-for-the-official-speedtest-net-cli-version)

[4] [https://github.com](https://github.com/LeonStraathof/pfsense-speedtest-widget)

[5] [https://forum.netgate.com](https://forum.netgate.com/topic/64735/speedtest-cli-run-speedtest-on-pfsense-box/54?page=8)

[6] [https://github.com](https://github.com/LeonStraathof/pfsense-speedtest-widget)

[7] [https://github.com](https://github.com/aln-1/pfsense-speedtest-widget)

[8] [https://forum.netgate.com](https://forum.netgate.com/topic/64735/speedtest-cli-run-speedtest-on-pfsense-box/158)

[9] [https://forums.lawrencesystems.com](https://forums.lawrencesystems.com/t/speedtest-from-the-pfsense-dashboard/19954)
