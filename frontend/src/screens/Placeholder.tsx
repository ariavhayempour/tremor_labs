import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
export function Placeholder({ title }: { title: string }) {
  return <><span className="eyebrow">{copy.development}</span><h1>{title}</h1><section className="panel placeholder"><span className="icon-tile"><Icon name="wave" size={36}/></span><h2>{copy.pending}</h2><p>{copy.pendingBody}</p><Link className="button primary" to="/">{copy.back}<Icon name="arrow"/></Link></section></>
}
