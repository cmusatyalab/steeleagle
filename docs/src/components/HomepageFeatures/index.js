import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';
import { Icon } from "@iconify/react";

const FeatureList = [
  {
    title: 'Accessible',
    icon: 'healthicons:entry',
    description: (
      <>
        SteelEagle lowers the barrier to entry for autonomous robotics by abstracting away disparate control schemes and providing a high level domain-specific language for writing missions.
      </>
    ),
  },
  {
    title: 'Lightweight',
    icon: 'noto:baby-chick',
    description: (
      <>
        Leveraging the edge for compute, SteelEagle enables autonomy on aircraft significantly smaller and lighter than traditional autonomous UAVs.
      </>
    ),
  },
  {
    title: 'Portable',
    icon: 'noto:floppy-disk',
    description: (
      <>
        Agnostic by design, Steeleagle supports heterogenous vehicle swarms allowing users to focus on the mission and worry less about the idiosyncrasies of the platforms available for that mission.
      </>
    ),
  },
  {
    title: 'BVLOS (Beyond Visual Line-of-Sight)',
    icon: 'flat-color-icons:binoculars',
    description: (
      <>
        SteelEagle vehicles can communicate with an edge backend using any type of underlying radio communication, including LTE, without human supervision.
      </>
    ),
  },
  {
    title: 'Scalable',
    icon: 'bi:gpu-card',
    description: (
      <>
        Utilizing edge computing allows SteelEagle vehicles to run computational expensive AI without carrying everything on board. As new AI technology emerges or edge hardware improves, all vehicles benefit without upgrading or retrofitting them.
      </>
    ),
  },
  {
    title: 'Extensible',
    icon: 'dashicons:plugins-checked',
    description: (
      <>
        Designed for extensibility, developers can plug in their own components (vehicle-specific drivers, custom GCS apps, alternative mission control schemes) as long they adhere to the API specification.
      </>
    ),
  },
];

function Feature({icon, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Icon icon={icon} widht='72px' height='72px'/>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
