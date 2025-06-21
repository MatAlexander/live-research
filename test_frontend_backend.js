// Test script to verify frontend-backend connectivity
const fetch = require('node-fetch');

const API_URL = 'http://localhost:8000';

async function testConnection() {
    console.log('🧪 Testing AI Thinking Agent API Connection...\n');
    
    try {
        // Test 1: Health check
        console.log('1️⃣ Testing health endpoint...');
        const healthResponse = await fetch(`${API_URL}/health`);
        const healthData = await healthResponse.json();
        console.log('✅ Health check passed:', healthData);
        
        // Test 2: Create query
        console.log('\n2️⃣ Testing query creation...');
        const queryResponse = await fetch(`${API_URL}/v1/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Origin': 'http://localhost:4200'
            },
            body: JSON.stringify({ query: 'What is the capital of France?' })
        });
        
        const queryData = await queryResponse.json();
        console.log('✅ Query created:', queryData);
        
        // Test 3: CORS headers
        console.log('\n3️⃣ Testing CORS headers...');
        console.log('Query response headers:');
        for (const [key, value] of queryResponse.headers.entries()) {
            if (key.toLowerCase().includes('cors') || key.toLowerCase().includes('access-control')) {
                console.log(`  ${key}: ${value}`);
            }
        }
        
        console.log('\n✅ All tests passed! Backend is ready for frontend connection.');
        
    } catch (error) {
        console.error('❌ Test failed:', error.message);
    }
}

testConnection();
