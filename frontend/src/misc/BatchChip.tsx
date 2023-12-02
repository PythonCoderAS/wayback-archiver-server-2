import ListAltIcon from '@mui/icons-material/ListAlt';
import { Chip } from '@mui/material';
import { Link } from 'react-router-dom';

export default function BatchChip({batchId}: { batchId: number} ) {
    return (
        <Chip color='secondary' clickable={true} icon={<ListAltIcon />} label={'Batch ' + batchId} component={Link} to={`/batch/${batchId}`} />
    )
}