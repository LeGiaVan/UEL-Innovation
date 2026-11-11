import assert from 'node:assert/strict'
import {pathToFileURL} from 'node:url'
import path from 'node:path'
const frontend=process.env.FRONTEND_ROOT
const {createServer}=await import(pathToFileURL(path.join(frontend,'node_modules/vite/dist/node/index.js')))
process.env.VITE_MOCK_API='false'
const vite=await createServer({root:frontend,optimizeDeps:{noDiscovery:true,include:[]},server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'})
try {
 const {store}=await vite.ssrLoadModule('/src/store/store.js')
 const {login,logout}=await vite.ssrLoadModule('/src/store/slices/authSlice.js')
 const {fetchChatModes,setSelectedMode}=await vite.ssrLoadModule('/src/store/slices/modeSlice.js')
 const {fetchQA}=await vite.ssrLoadModule('/src/store/slices/qaSlice.js')
 const {sendMessage,fetchConversation,fetchConversationList}=await vite.ssrLoadModule('/src/store/slices/chatSlice.js')
 const {getAccessToken}=await vite.ssrLoadModule('/src/api/session.js')
 const {default:api,API_URL,MOCK_API}=await vite.ssrLoadModule('/src/api/client.js')
 const {default:department}=await vite.ssrLoadModule('/src/config/department.json')
 assert.equal(MOCK_API,false)
 const user=await store.dispatch(login({username:'integration',password:process.env.TEST_PASSWORD})).unwrap()
 assert.ok(user.memberships.some(m=>m.department===department.id))
 await store.dispatch(fetchChatModes()).unwrap()
 await store.dispatch(fetchQA()).unwrap()
 store.dispatch(setSelectedMode('module_1'))
 assert.equal(store.getState().mode.modes.length,4)
 const question=store.getState().qa.questions[0]
 await store.dispatch(sendMessage({message:question.question})).unwrap()
 assert.ok(store.getState().chat.messages.at(-1).content.includes(question.answer))
 const id=store.getState().chat.conversationId
 await store.dispatch(fetchConversation(id)).unwrap()
 assert.equal(store.getState().chat.messages.length,2)
 await store.dispatch(fetchConversationList()).unwrap()
 const lists=await api.get(`${API_URL}/conversations`)
 assert.ok(lists.data.conversations.some(c=>c.id===id))
 await store.dispatch(logout()).unwrap()
 assert.equal(getAccessToken(),null)
 assert.equal(store.getState().auth.user,null)
 assert.equal(store.getState().chat.messages.length,0)
 await assert.rejects(()=>api.get(`${API_URL}/auth/me`))
 console.log(`PASS live FE → FastAPI: ${department.id} login, modes, QA, SSE, history, logout`)
} finally {await vite.close()}
