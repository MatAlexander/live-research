// Simple test script to verify tool events are working
const API_URL = 'http://localhost:8000';

async function testToolEvents() {
    console.log('🧪 Testing tool events...');
    
    try {
        // 1. Test backend health
        console.log('1. Testing backend connection...');
        const healthResponse = await fetch(`${API_URL}/health`);
        const healthData = await healthResponse.json();
        console.log('✅ Backend healthy:', healthData);
        
        // 2. Create a query
        console.log('2. Creating test query...');
        const queryResponse = await fetch(`${API_URL}/v1/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: 'What is quantum computing?',
                model: 'o4-mini'
            })
        });
        
        const queryData = await queryResponse.json();
        console.log('✅ Query created:', queryData);
        
        // 3. Listen to event stream
        console.log('3. Listening to event stream...');
        const eventSource = new EventSource(`${API_URL}/v1/stream/${queryData.run_id}`);
        
        let toolUseEvents = [];
        let toolResultEvents = [];
        let thoughtEvents = [];
        let finalAnswerEvents = [];
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log(`📡 Event received: ${data.type}`, data);
                
                switch (data.type) {
                    case 'tool_use':
                        toolUseEvents.push(data);
                        console.log(`🔧 Tool Use: ${data.tool} - ${data.action}`);
                        break;
                    case 'tool_result':
                        toolResultEvents.push(data);
                        console.log(`✅ Tool Result: ${data.tool} - ${data.result}`);
                        break;
                    case 'thought':
                        thoughtEvents.push(data);
                        console.log(`🧠 Thought: ${data.text.substring(0, 100)}...`);
                        break;
                    case 'final_answer':
                        finalAnswerEvents.push(data);
                        console.log(`💡 Final Answer: ${data.text.substring(0, 100)}...`);
                        break;
                    case 'complete':
                        console.log('✅ Query completed!');
                        console.log('\n📊 Event Summary:');
                        console.log(`Tool Use Events: ${toolUseEvents.length}`);
                        console.log(`Tool Result Events: ${toolResultEvents.length}`);
                        console.log(`Thought Events: ${thoughtEvents.length}`);
                        console.log(`Final Answer Events: ${finalAnswerEvents.length}`);
                        
                        if (toolUseEvents.length > 0) {
                            console.log('\n🔧 Tool Use Events Details:');
                            toolUseEvents.forEach((event, i) => {
                                console.log(`  ${i+1}. ${event.tool}: ${event.action} - ${event.details}`);
                            });
                        }
                        
                        if (toolResultEvents.length > 0) {
                            console.log('\n✅ Tool Result Events Details:');
                            toolResultEvents.forEach((event, i) => {
                                console.log(`  ${i+1}. ${event.tool}: ${event.result}`);
                            });
                        }
                        
                        eventSource.close();
                        break;
                    case 'error':
                        console.error('❌ Error:', data.message);
                        eventSource.close();
                        break;
                }
            } catch (e) {
                console.error('Error parsing event:', e);
            }
        };
        
        eventSource.onerror = (error) => {
            console.error('❌ SSE Error:', error);
            eventSource.close();
        };
        
    } catch (error) {
        console.error('❌ Test failed:', error);
    }
}

// Run the test
testToolEvents();
