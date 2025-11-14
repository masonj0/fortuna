from playwright.sync_api import sync_playwright, expect
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock the Electron API and the WebSocket connection
    page.add_init_script("""
        window.electronAPI = {
            getApiKey: () => Promise.resolve('test-api-key'),
            getBackendStatus: () => Promise.resolve({ state: 'running', logs: [] }),
            onBackendStatusUpdate: (callback) => {
                // Do nothing, assume it's always running
                return () => {}; // Return an unsubscribe function
            }
        };

        const mockSocket = {
            listeners: {},
            on(event, callback) {
                this.listeners[event] = callback;
            },
            close() {},
            readyState: 0, // Initially connecting
            send() {},
        };
        window.mockSocket = mockSocket;
        window.WebSocket = function(url) {
            console.log('Mock WebSocket created for:', url);
            setTimeout(() => {
                mockSocket.readyState = 1; // OPEN
                if(mockSocket.listeners.open) {
                    mockSocket.listeners.open();
                }
            }, 100);
            return mockSocket;
        };
    """)

    # Intercept the API call and return a mock response
    page.route("**/api/adapters/status", lambda route: route.fulfill(
        status=200,
        json=[]
    ))

    page.goto("http://localhost:3000")

    # Wait for the status indicator to be visible
    page.wait_for_selector('[data-testid="status-indicator"]')

    # Check that the status indicator eventually shows "Live"
    expect(page.locator('[data-testid="status-indicator"]')).to_have_text("Live", timeout=5000)

    # Simulate a WebSocket message with race data
    page.evaluate("""
        window.mockSocket.listeners.message({
            data: JSON.stringify({
                races: [{
                    id: 'test-race-1',
                    venue: 'Test Park',
                    raceNumber: 1,
                    isErrorPlaceholder: false,
                    startTime: new Date().toISOString(),
                    runners: [{
                        number: 1,
                        name: 'Test Horse',
                        odds: { 'TestSource': { win: 5.0, source: 'TestSource', last_updated: new Date().toISOString() } }
                    }]
                }],
                source_info: [{
                    name: 'TestSource',
                    status: 'SUCCESS',
                    races_fetched: 1,
                    fetch_duration: 0.1
                }]
            })
        });
    """)

    # Check that the UI has updated with the new data
    expect(page.get_by_text("Test Park")).to_be_visible()
    expect(page.get_by_text("Test Horse")).to_be_visible()

    page.screenshot(path="jules-scratch/verification/websockets.png")
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
