import { Phone, Mail, MapPin, User } from 'lucide-react'
import './ContactInfo.css'

const ContactInfo = ({ messages }) => {
  const lastAssistantMessage = [...messages].reverse().find(
    (msg) => msg.role === 'assistant' && msg.contactInfo
  )

  if (!lastAssistantMessage?.contactInfo) {
    return null
  }

  const { contactInfo } = lastAssistantMessage

  return (
    <div className="contact-info">
      <div className="contact-info-header">
        <h3>Thông Tin Liên Hệ</h3>
      </div>
      <div className="contact-info-content">
        {contactInfo.person && (
          <div className="contact-item">
            <User size={18} />
            <span><strong>Người phụ trách:</strong> {contactInfo.person}</span>
          </div>
        )}
        {contactInfo.department && (
          <div className="contact-item">
            <MapPin size={18} />
            <span><strong>Phòng/Ban:</strong> {contactInfo.department}</span>
          </div>
        )}
        {contactInfo.phone && (
          <div className="contact-item">
            <Phone size={18} />
            <span><strong>Điện thoại:</strong> {contactInfo.phone}</span>
          </div>
        )}
        {contactInfo.email && (
          <div className="contact-item">
            <Mail size={18} />
            <span><strong>Email:</strong> {contactInfo.email}</span>
          </div>
        )}
        {contactInfo.address && (
          <div className="contact-item">
            <MapPin size={18} />
            <span><strong>Địa chỉ:</strong> {contactInfo.address}</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default ContactInfo
