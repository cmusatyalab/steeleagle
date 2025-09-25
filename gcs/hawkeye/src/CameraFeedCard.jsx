import { useState, useEffect } from 'react';
import Card from 'react-bootstrap/Card';

function CameraFeedCard() {
  return(
    <>
      <Card bg='dark' text='light' border='light' style={{ width: '18rem' }}>
	  <Card.Img variant="top" src="holder.js/100px180" />
	  <Card.Title className="text-center">baldeagle</Card.Title>
	  <Card.Footer className="text-center">Last updated 3 mins ago</Card.Footer>
      </Card>
    </>
  );
}

export default CameraFeedCard;
