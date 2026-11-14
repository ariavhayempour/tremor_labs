import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
export function CheckIn() {
  return <><span className="eyebrow">{copy.development}</span><h1>{copy.previewTitle}</h1><p className="lead">{copy.previewBody}</p><div className="preparation"><Icon name="shield"/><div><h3>{copy.ready}</h3><p>{copy.readyBody}</p></div></div><div className="step-grid">{copy.steps.map(step => <article className="step-card" key={step.name}><span className="icon-tile"><Icon name={step.icon}/></span><h3>{step.name}</h3><p>{step.body}</p><span className="muted">{step.time}</span></article>)}</div><Link className="button primary top-space" to="/">{copy.back}<Icon name="arrow"/></Link></>
}
