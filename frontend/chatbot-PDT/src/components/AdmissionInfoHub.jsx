import { Link } from 'react-router-dom'
import { ADMISSION_INFO_SLUG, ADMISSION_PANEL_CARDS } from '../config/admissionReference'
import './AdmissionInfoHub.css'

const HUB = `/bot/${ADMISSION_INFO_SLUG}`

const AdmissionInfoHub = () => {
  return (
    <div className="admission-info-hub" aria-label="Khu vực Thông tin tuyển sinh">
      <h1 className="admission-info-hub__title">Thông tin tuyển sinh</h1>
      <ul className="admission-info-hub__cards" role="list">
        {ADMISSION_PANEL_CARDS.map((c) => (
          <li key={c.key} className="admission-info-hub__li">
            <Link
              to={HUB}
              className={`admission-info-hub__card admission-info-hub__card--${c.key}`}
              replace
            >
              <h2 className="admission-info-hub__card-title">{c.title}</h2>
              <p className="admission-info-hub__card-body">{c.body}</p>
              {c.iconImage ? (
                <span className="admission-info-hub__card-icon" aria-hidden="true">
                  <img
                    className="admission-info-hub__card-icon-img"
                    src={`${import.meta.env.BASE_URL}${c.iconImage}`}
                    alt=""
                    width={96}
                    height={96}
                    loading="lazy"
                    decoding="async"
                  />
                </span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default AdmissionInfoHub
