"""
反自动化检测脚本。
在页面加载前注入，隐藏 Playwright 自动化标记。
"""

STEALTH_SCRIPT = """
// 移除 navigator.webdriver 标记
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// 伪造 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// 伪造 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en']
});

// 伪造 platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32'
});
"""


def apply_stealth(context):
    """在所有新页面加载前注入反检测脚本。"""
    context.add_init_script(STEALTH_SCRIPT)
