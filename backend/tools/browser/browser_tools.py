"""Individual browser automation tools using Playwright."""

import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, Optional, List
from strands import tool
from .browser_manager import BrowserManager
import os

# Create global browser manager instance with region from environment or default
region = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')
browser_manager = BrowserManager(region=region)

logger = logging.getLogger(__name__)


@tool
def browser_install() -> str:
    """Install and initialize the browser automation system.
    
    This creates a new browser session and returns the session ID for use in other browser tools.
    
    Returns:
        Session ID that can be used with other browser tools.
    """
    try:
        # Update region from environment if changed
        current_region = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')
        if browser_manager.region != current_region:
            browser_manager.region = current_region
            logger.info(f"Updated browser manager region to: {current_region}")
        
        # Run async operations properly
        async def async_install():
            await browser_manager._async_initialize()
            return await browser_manager._async_create_session()
        
        # Handle async execution with uvloop compatibility
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use thread executor
                import concurrent.futures
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(async_install())
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_new_loop)
                    session_id = future.result(timeout=30)
            else:
                session_id = loop.run_until_complete(async_install())
        except RuntimeError:
            # No event loop, create one
            session_id = asyncio.run(async_install())
        
        return f"Browser installed successfully. Session ID: {session_id}"
    except Exception as e:
        logger.error(f"Failed to install browser: {e}")
        return f"Error installing browser: {str(e)}"


@tool
def browser_navigate(session_id: str, url: str) -> str:
    """Navigate to a URL in the browser.
    
    Args:
        session_id: Browser session ID from browser_install
        url: URL to navigate to
        
    Returns:
        Success or error message
    """
    try:
        # Update region from environment if changed
        current_region = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')
        if browser_manager.region != current_region:
            browser_manager.region = current_region
            logger.info(f"Updated browser manager region to: {current_region}")
            
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _navigate():
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            return f"Successfully navigated to {url}"
        
        return browser_manager._run_async(_navigate())
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return f"Error navigating to {url}: {str(e)}"


@tool
def browser_click(session_id: str, selector: str) -> str:
    """Click on an element in the browser.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector for the element to click
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _click():
            await page.click(selector)
            return f"Successfully clicked element: {selector}"
        
        return browser_manager._run_async(_click())
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return f"Error clicking {selector}: {str(e)}"


@tool
def browser_type(session_id: str, selector: str, text: str) -> str:
    """Type text into an input field.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector for the input element
        text: Text to type
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _type():
            await page.fill(selector, text)
            return f"Successfully typed text into {selector}"
        
        return browser_manager._run_async(_type())
    except Exception as e:
        logger.error(f"Type failed: {e}")
        return f"Error typing into {selector}: {str(e)}"


@tool
def browser_fill_form(session_id: str, form_data: Dict[str, str]) -> str:
    """Fill multiple form fields at once.
    
    Args:
        session_id: Browser session ID
        form_data: Dictionary mapping CSS selectors to values
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _fill_form():
            for selector, value in form_data.items():
                await page.fill(selector, value)
            return f"Successfully filled {len(form_data)} form fields"
        
        return browser_manager._run_async(_fill_form())
    except Exception as e:
        logger.error(f"Form fill failed: {e}")
        return f"Error filling form: {str(e)}"


@tool
def browser_take_screenshot(session_id: str, path: str = None) -> str:
    """Take a screenshot of the current page.
    
    Args:
        session_id: Browser session ID
        path: Optional path to save screenshot (defaults to screenshots/ directory)
        
    Returns:
        Path to saved screenshot or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _screenshot():
            screenshots_dir = "screenshots"
            os.makedirs(screenshots_dir, exist_ok=True)
            
            if not path:
                filename = f"screenshot_{int(time.time())}.png"
                screenshot_path = os.path.join(screenshots_dir, filename)
            else:
                screenshot_path = path if os.path.isabs(path) else os.path.join(screenshots_dir, path)
            
            await page.screenshot(path=screenshot_path)
            return f"Screenshot saved to {screenshot_path}"
        
        return browser_manager._run_async(_screenshot())
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return f"Error taking screenshot: {str(e)}"


@tool
def browser_evaluate(session_id: str, script: str) -> str:
    """Execute JavaScript code in the browser.
    
    Args:
        session_id: Browser session ID
        script: JavaScript code to execute
        
    Returns:
        Result of script execution or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _evaluate():
            result = await page.evaluate(script)
            return f"Script result: {result}"
        
        return browser_manager._run_async(_evaluate())
    except Exception as e:
        logger.error(f"Script evaluation failed: {e}")
        return f"Error executing script: {str(e)}"


@tool
def browser_wait_for(session_id: str, selector: str, timeout: int = 30000) -> str:
    """Wait for an element to appear on the page.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector to wait for
        timeout: Timeout in milliseconds (default: 30000)
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _wait():
            await page.wait_for_selector(selector, timeout=timeout)
            return f"Element {selector} appeared on page"
        
        return browser_manager._run_async(_wait())
    except Exception as e:
        logger.error(f"Wait failed: {e}")
        return f"Error waiting for {selector}: {str(e)}"


@tool
def browser_press_key(session_id: str, key: str) -> str:
    """Press a keyboard key.
    
    Args:
        session_id: Browser session ID
        key: Key to press (e.g., 'Enter', 'Tab', 'Escape')
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _press():
            await page.keyboard.press(key)
            return f"Successfully pressed key: {key}"
        
        return browser_manager._run_async(_press())
    except Exception as e:
        logger.error(f"Key press failed: {e}")
        return f"Error pressing key {key}: {str(e)}"


@tool
def browser_hover(session_id: str, selector: str) -> str:
    """Hover over an element.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector for the element to hover over
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _hover():
            await page.hover(selector)
            return f"Successfully hovered over: {selector}"
        
        return browser_manager._run_async(_hover())
    except Exception as e:
        logger.error(f"Hover failed: {e}")
        return f"Error hovering over {selector}: {str(e)}"


@tool
def browser_select_option(session_id: str, selector: str, value: str) -> str:
    """Select an option from a dropdown.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector for the select element
        value: Value to select
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _select():
            await page.select_option(selector, value)
            return f"Successfully selected {value} in {selector}"
        
        return browser_manager._run_async(_select())
    except Exception as e:
        logger.error(f"Select failed: {e}")
        return f"Error selecting option in {selector}: {str(e)}"


@tool
def browser_file_upload(session_id: str, selector: str, file_path: str) -> str:
    """Upload a file to a file input.
    
    Args:
        session_id: Browser session ID
        selector: CSS selector for the file input element
        file_path: Path to the file to upload
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        if not os.path.exists(file_path):
            return f"Error: File {file_path} does not exist"
        
        async def _upload():
            await page.set_input_files(selector, file_path)
            return f"Successfully uploaded {file_path} to {selector}"
        
        return browser_manager._run_async(_upload())
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return f"Error uploading file: {str(e)}"


@tool
def browser_handle_dialog(session_id: str, action: str, text: str = "") -> str:
    """Handle browser dialogs (alert, confirm, prompt).
    
    Args:
        session_id: Browser session ID
        action: Action to take ('accept' or 'dismiss')
        text: Text to enter for prompt dialogs
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _handle_dialog():
            def dialog_handler(dialog):
                if action == "accept":
                    if text:
                        dialog.accept(text)
                    else:
                        dialog.accept()
                else:
                    dialog.dismiss()
            
            page.on("dialog", dialog_handler)
            return f"Dialog handler set for {action}"
        
        return browser_manager._run_async(_handle_dialog())
    except Exception as e:
        logger.error(f"Dialog handling failed: {e}")
        return f"Error handling dialog: {str(e)}"


@tool
def browser_drag(session_id: str, source_selector: str, target_selector: str) -> str:
    """Drag and drop from source to target element.
    
    Args:
        session_id: Browser session ID
        source_selector: CSS selector for the source element
        target_selector: CSS selector for the target element
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _drag():
            await page.drag_and_drop(source_selector, target_selector)
            return f"Successfully dragged from {source_selector} to {target_selector}"
        
        return browser_manager._run_async(_drag())
    except Exception as e:
        logger.error(f"Drag and drop failed: {e}")
        return f"Error dragging element: {str(e)}"


@tool
def browser_resize(session_id: str, width: int, height: int) -> str:
    """Resize the browser viewport.
    
    Args:
        session_id: Browser session ID
        width: Viewport width in pixels
        height: Viewport height in pixels
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _resize():
            await page.set_viewport_size({"width": width, "height": height})
            return f"Successfully resized viewport to {width}x{height}"
        
        return browser_manager._run_async(_resize())
    except Exception as e:
        logger.error(f"Resize failed: {e}")
        return f"Error resizing viewport: {str(e)}"


@tool
def browser_tabs(session_id: str, action: str, tab_id: str = None, url: str = None) -> str:
    """Manage browser tabs (create, switch, close, list).
    
    Args:
        session_id: Browser session ID
        action: Action to perform ('create', 'switch', 'close', 'list')
        tab_id: Tab ID for switch/close actions
        url: URL for new tab creation
        
    Returns:
        Success message or tab information
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        async def _manage_tabs():
            if action == "create":
                new_page = await session.context.new_page()
                new_tab_id = f"tab_{len(session.pages)}"
                session.add_page(new_tab_id, new_page)
                if url:
                    await new_page.goto(url)
                return f"Created new tab: {new_tab_id}"
            
            elif action == "switch":
                if not tab_id or not session.switch_page(tab_id):
                    return f"Error: Tab {tab_id} not found"
                return f"Switched to tab: {tab_id}"
            
            elif action == "close":
                if not tab_id or tab_id not in session.pages:
                    return f"Error: Tab {tab_id} not found"
                await session.pages[tab_id].close()
                session.remove_page(tab_id)
                return f"Closed tab: {tab_id}"
            
            elif action == "list":
                tabs_info = {}
                for page_id, page in session.pages.items():
                    tabs_info[page_id] = {
                        "url": page.url,
                        "active": page_id == session.active_page_id
                    }
                return json.dumps(tabs_info, indent=2)
            
            else:
                return f"Error: Unknown action {action}"
        
        return browser_manager._run_async(_manage_tabs())
    except Exception as e:
        logger.error(f"Tab management failed: {e}")
        return f"Error managing tabs: {str(e)}"


@tool
def browser_navigate_back(session_id: str) -> str:
    """Navigate back in browser history.
    
    Args:
        session_id: Browser session ID
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _back():
            await page.go_back()
            return "Successfully navigated back"
        
        return browser_manager._run_async(_back())
    except Exception as e:
        logger.error(f"Navigate back failed: {e}")
        return f"Error navigating back: {str(e)}"


@tool
def browser_snapshot(session_id: str, selector: str = None) -> str:
    """Get HTML content of page or element.
    
    Args:
        session_id: Browser session ID
        selector: Optional CSS selector for specific element
        
    Returns:
        HTML content or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _snapshot():
            if selector:
                element = await page.query_selector(selector)
                if not element:
                    return f"Error: Element {selector} not found"
                html = await element.inner_html()
            else:
                html = await page.content()
            
            # Truncate long HTML
            if len(html) > 2000:
                html = html[:2000] + "... [truncated]"
            
            return html
        
        return browser_manager._run_async(_snapshot())
    except Exception as e:
        logger.error(f"Snapshot failed: {e}")
        return f"Error getting snapshot: {str(e)}"


@tool
def browser_network_requests(session_id: str, action: str = "start") -> str:
    """Monitor network requests.
    
    Args:
        session_id: Browser session ID
        action: Action to perform ('start' or 'stop')
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _network():
            if action == "start":
                def log_request(request):
                    logger.info(f"Request: {request.method} {request.url}")
                
                page.on("request", log_request)
                return "Network request monitoring started"
            else:
                page.remove_all_listeners("request")
                return "Network request monitoring stopped"
        
        return browser_manager._run_async(_network())
    except Exception as e:
        logger.error(f"Network monitoring failed: {e}")
        return f"Error with network monitoring: {str(e)}"


@tool
def browser_console_messages(session_id: str, action: str = "start") -> str:
    """Monitor console messages.
    
    Args:
        session_id: Browser session ID
        action: Action to perform ('start' or 'stop')
        
    Returns:
        Success or error message
    """
    try:
        session = browser_manager.get_session(session_id)
        if not session:
            return f"Error: Session {session_id} not found"
        
        page = session.get_active_page()
        if not page:
            return "Error: No active page in session"
        
        async def _console():
            if action == "start":
                def log_console(msg):
                    logger.info(f"Console {msg.type}: {msg.text}")
                
                page.on("console", log_console)
                return "Console message monitoring started"
            else:
                page.remove_all_listeners("console")
                return "Console message monitoring stopped"
        
        return browser_manager._run_async(_console())
    except Exception as e:
        logger.error(f"Console monitoring failed: {e}")
        return f"Error with console monitoring: {str(e)}"


@tool
def browser_close(session_id: str) -> str:
    """Close a browser session.
    
    Args:
        session_id: Browser session ID to close
        
    Returns:
        Success or error message
    """
    try:
        browser_manager.close_session(session_id)
        return f"Successfully closed session: {session_id}"
    except Exception as e:
        logger.error(f"Close session failed: {e}")
        return f"Error closing session: {str(e)}"