import { useRef, useEffect, useState } from 'react'
import { Editor } from 'primereact/editor';

function PlanPage() {
    const [editorContent, setEditorContent] = useState('');
    return (
        <>
            <Editor value={editorContent} onTextChange={(e) => setEditorContent(e.htmlValue)} style={{ height: '320px' }} />
        </>
    );

}

export default PlanPage;
