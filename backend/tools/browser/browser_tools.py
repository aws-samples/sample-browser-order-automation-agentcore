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
import asyncio
import concurrent.futures

# Get global browser manager instance (singleton)
def get_browser_manager():
    region = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')
    return BrowserManager(region=region)

browser_manager = get_browser_manager()

def run_async_safely(coro):
    """Safely run async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    # Add timeout to prevent hanging
                    return new_loop.run_until_complete(
                        asyncio.wait_for(coro, timeout=60.0)  # 60 second overall timeout
                    )
                except asyncio.TimeoutError:
                    logger.error("Async operation timed out after 60 seconds")
                    raise TimeoutError("Browser operation timed out")
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=70)  # Slightly longer than inner timeout
        else:
            return loop.run_until_complete(asyncio.wait_for(coro, timeout=60.0))
    except RuntimeError:
        return asyncio.run(asyncio.wait_for(coro, timeout=60.0))
    except (asyncio.TimeoutError, concurrent.futures.TimeoutError, TimeoutError) as e:
        logger.error(f"Browser operation timed out: {e}")
        return f"Error: Operation timed out after 60 seconds"

logger = logging.getLogger(__name__)


@tool
def browser_install() -> str:
    """Install and initialize the browser automation system.
    
    This creates a new browser session and returns the session ID for use in other browser tools.
    
    Returns:
        Session ID that can be used with other browser tools.
    """
    logger.info("browser_install called - starting browser installation")
    try:
        # Get current browser manager instance
        browser_manager = get_browser_manager()
        logger.info(f"Got browser manager: {browser_manager}")
        
        # Run async operations properly
        async def async_install():
            logger.info("Initializing browser manager...")
            await browser_manager._async_initialize()
            logger.info("Creating browser session...")
            session_id = await browser_manager._async_create_session()
            logger.info(f"Created session: {session_id}")
            return session_id
        
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
        
        result = f"Browser installed successfully. Session ID: {session_id}"
        logger.info(f"browser_install completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to install browser: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
    logger.info(f"browser_navigate called - session_id: {session_id}, url: {url}")
    try:
        # Get current browser manager instance
        browser_manager = get_browser_manager()
        session = browser_manager.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found in browser manager")
            return f"Error: Session {session_id} not found"
        
        logger.info(f"Found session: {session}")
        page = session.get_active_page()
        if not page:
            logger.error("No active page in session")
            return "Error: No active page in session"
        
        logger.info(f"Got active page: {page}")
        
        async def _navigate():
            logger.info(f"Starting navigation to {url}")
            try:
                # Add timeout and better error handling
                await page.goto(url, timeout=30000)  # 30 second timeout
                logger.info("Page loaded, waiting for domcontentloaded")
                await page.wait_for_load_state("domcontentloaded", timeout=15000)  # 15 second timeout
                logger.info(f"Navigation completed to {url}")
                return f"Successfully navigated to {url}"
            except Exception as nav_error:
                logger.error(f"Navigation error: {nav_error}")
                # Try to get current URL to see if partial navigation worked
                try:
                    current_url = page.url
                    logger.info(f"Current page URL: {current_url}")
                    if current_url != "about:blank":
                        return f"Partially navigated to {current_url} (timeout occurred)"
                except Exception:
                    pass
                raise nav_error
        
        result = run_async_safely(_navigate())
        logger.info(f"browser_navigate completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        
        return run_async_safely(_click())
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
        
        return run_async_safely(_type())
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
        
        return run_async_safely(_fill_form())
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
        
        return run_async_safely(_screenshot())
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
        
        return run_async_safely(_evaluate())
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
        
        return run_async_safely(_wait())
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
        
        return run_async_safely(_press())
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
        
        return run_async_safely(_hover())
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
        
        return run_async_safely(_select())
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
        
        return run_async_safely(_upload())
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
        
        return run_async_safely(_handle_dialog())
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
        
        return run_async_safely(_drag())
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
        
        return run_async_safely(_resize())
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
        
        return run_async_safely(_manage_tabs())
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
        
        return run_async_safely(_back())
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
            try:
                # Get current URL first
                current_url = page.url
                logger.info(f"Taking snapshot of page: {current_url}")
                
                if selector:
                    element = await page.query_selector(selector)
                    if not element:
                        return f"Error: Element {selector} not found on {current_url}"
                    html = await element.inner_html()
                else:
                    html = await page.content()
                
                # Truncate long HTML
                if len(html) > 2000:
                    html = html[:2000] + "... [truncated]"
                
                return f"Page: {current_url}\n\nHTML Content:\n{html}"
            except Exception as e:
                logger.error(f"Snapshot error: {e}")
                return f"Error taking snapshot: {str(e)}"
        
        return run_async_safely(_snapshot())
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
        
        return run_async_safely(_network())
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
        
        return run_async_safely(_console())
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