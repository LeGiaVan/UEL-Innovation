import department from '../config/department.json'
import { FALLBACK_CHAT_MODES } from '../constants/chatModes'
const conversations = new Map()
const json = (data, status=200) => new Response(JSON.stringify(data), {status,headers:{'Content-Type':'application/json'}})
export async function mockRequest(url, options={}) {
 if(options.signal?.aborted) throw new DOMException('Aborted','AbortError')
 const path = new URL(url, 'http://localhost').pathname.replace(/^.*\/api/, '')
 if(path === '/chat/modes') return json({modes:FALLBACK_CHAT_MODES})
 if(path === '/qa') return json(department.topics.map((t,i)=>({id:String(i+1),mode:`module_${i+1}`,question:t[2],answer:t[3]})))
 if(path === '/chat/stream') {
  const body=JSON.parse(options.body || '{}')
  const topic=department.topics[Number(body.mode?.split('_')[1])-1] || department.topics[0]
  const matched=department.topics.find(t=>t[2]===body.message)
  const response=(matched || topic)[3]
  const id=body.conversation_id || `demo-${crypto.randomUUID()}`
  const rows=conversations.get(id) || []
  rows.push({user_message:body.message,assistant_response:response,timestamp:new Date().toISOString()})
  conversations.set(id,rows)
  const encoder=new TextEncoder()
  const events=[...response.match(/.{1,24}/gu)].map(text=>({type:'token',text}))
  events.push({type:'done',response,conversation_id:id,resolved_mode:body.mode,citations:[],user_message:body.message})
  const stream=new ReadableStream({pull(controller){
   if(options.signal?.aborted){controller.error(new DOMException('Aborted','AbortError'));return}
   const event=events.shift()
   if(event)controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));else controller.close()
  }})
  return new Response(stream,{headers:{'Content-Type':'text/event-stream'}})
 }
 if(path === '/conversations')return json({conversations:[...conversations.entries()].map(([id,messages])=>({conversation_id:id,preview:messages[0]?.user_message}))})
 if(path.startsWith('/conversations/')) {
  const id=decodeURIComponent(path.split('/').pop())
  return conversations.has(id)?json({conversation_id:id,messages:conversations.get(id)}):json({detail:'Không tìm thấy hội thoại mô phỏng.'},404)
 }
 return json({detail:'Chức năng này chưa có API mô phỏng của phòng.'},501)
}
