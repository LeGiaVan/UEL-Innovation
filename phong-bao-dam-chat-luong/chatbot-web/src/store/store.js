import {configureStore,combineReducers} from '@reduxjs/toolkit'
import chat from './slices/chatSlice'
import qa from './slices/qaSlice'
import mode from './slices/modeSlice'
import auth from './slices/authSlice'
const combined=combineReducers({chat,qa,mode,auth})
export const store=configureStore({
 devTools: import.meta.env.DEV ? {
  actionSanitizer: action => action.type.startsWith('auth/login/')
   ? {...action,meta:{...action.meta,arg:{username:action.meta?.arg?.username,password:'[REDACTED]'}}}
   : action
 } : false,
 reducer:(state,action)=>{
  if (['auth/logout/fulfilled','auth/logout/rejected','auth/sessionExpired'].includes(action.type)) state=undefined
  return combined(state,action)
 }
})
