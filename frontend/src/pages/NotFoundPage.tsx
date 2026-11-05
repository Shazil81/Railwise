import {Link} from 'react-router-dom';
import {ArrowLeft, TrainFront} from 'lucide-react';

export default function NotFoundPage() {
  return <div className="rail-app"><main id="booking-main" tabIndex={-1} className="not-found-page">
    <TrainFront size={40} aria-hidden="true"/>
    <h1>We couldn’t find that page</h1>
    <p>The link may be incorrect or no longer available. Your bookings are available from Home.</p>
    <Link to="/" className="primary"><ArrowLeft size={18}/> Go to Home</Link>
  </main></div>;
}
