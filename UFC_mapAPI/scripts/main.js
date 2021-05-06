function initMap() {
       
    //define center of map
    const center = { lat: 15, lng: 0};
        
    // initializing the map
    let map = new google.maps.Map(document.getElementById("map"), {
    center: center,
    zoom: 3,
    minZoom: 2,
    maxZoom: 7,
	  mapTypeControl: true,
	  styles: [
    {
        "featureType": "administrative",
        "elementType": "labels.text.fill",
        "stylers": [
            {
                "color": "#6195a0"
            }
        ]
    },
    {
        "featureType": "administrative.province",
        "elementType": "geometry.stroke",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "landscape",
        "elementType": "geometry",
        "stylers": [
            {
                "lightness": "0"
            },
            {
                "saturation": "0"
            },
            {
                "color": "#f5f5f2"
            },
            {
                "gamma": "1"
            }
        ]
    },
    {
        "featureType": "landscape.man_made",
        "elementType": "all",
        "stylers": [
            {
                "lightness": "-3"
            },
            {
                "gamma": "1.00"
            }
        ]
    },
    {
        "featureType": "landscape.natural.terrain",
        "elementType": "all",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "poi",
        "elementType": "all",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "poi.park",
        "elementType": "geometry.fill",
        "stylers": [
            {
                "color": "#bae5ce"
            },
            {
                "visibility": "on"
            }
        ]
    },
    {
        "featureType": "road",
        "elementType": "all",
        "stylers": [
            {
                "saturation": -100
            },
            {
                "lightness": 45
            },
            {
                "visibility": "simplified"
            }
        ]
    },
    {
        "featureType": "road.highway",
        "elementType": "all",
        "stylers": [
            {
                "visibility": "simplified"
            }
        ]
    },
    {
        "featureType": "road.highway",
        "elementType": "geometry.fill",
        "stylers": [
            {
                "color": "#fac9a9"
            },
            {
                "visibility": "simplified"
            }
        ]
    },
    {
        "featureType": "road.highway",
        "elementType": "labels.text",
        "stylers": [
            {
                "color": "#4e4e4e"
            }
        ]
    },
    {
        "featureType": "road.arterial",
        "elementType": "labels.text.fill",
        "stylers": [
            {
                "color": "#787878"
            }
        ]
    },
    {
        "featureType": "road.arterial",
        "elementType": "labels.icon",
        "stylers": [
            {
                "visibility": "off"
            }
        ]
    },
    {
        "featureType": "transit",
        "elementType": "all",
        "stylers": [
            {
                "visibility": "simplified"
            }
        ]
    },
    {
        "featureType": "transit.station.airport",
        "elementType": "labels.icon",
        "stylers": [
            {
                "hue": "#0a00ff"
            },
            {
                "saturation": "-77"
            },
            {
                "gamma": "0.57"
            },
            {
                "lightness": "0"
            }
        ]
    },
    {
        "featureType": "transit.station.rail",
        "elementType": "labels.text.fill",
        "stylers": [
            {
                "color": "#43321e"
            }
        ]
    },
    {
        "featureType": "transit.station.rail",
        "elementType": "labels.icon",
        "stylers": [
            {
                "hue": "#ff6c00"
            },
            {
                "lightness": "4"
            },
            {
                "gamma": "0.75"
            },
            {
                "saturation": "-68"
            }
        ]
    },
    {
        "featureType": "water",
        "elementType": "all",
        "stylers": [
            {
                "color": "#eaf6f8"
            },
            {
                "visibility": "on"
            }
        ]
    },
    {
        "featureType": "water",
        "elementType": "geometry.fill",
        "stylers": [
            {
                "color": "#c7eced"
            }
        ]
    },
    {
        "featureType": "water",
        "elementType": "labels.text.fill",
        "stylers": [
            {
                "lightness": "-49"
            },
            {
                "saturation": "-53"
            },
            {
                "gamma": "0.79"
            }
        ]
    }
	]
	});  

	// icon for markers
    const pinIcon = {
	   url: "img/gym-icon.png",
	   scaledSize: new google.maps.Size(30, 45)
	}

    var infoWindow = null; // define info window outside to make it show once
    let infoArr = []; // array for info windows
    let markerArr = []; // array for markers
    let gymArr = []; // array for gym names
    let contentArr = []; // array for info-window content
    let positionsArr = []; // array for coordinates

    let gymName;
    let gymPosition;
    let gymLat;
    let athleteName;
    let athleteRank;
    let contentString;
    let newContentString;
    let marker;

    for(let i = 0; i < dataLocations.length; i++) {
        
        gymLat = dataLocations[i]["Location"].lat.toFixed(6);

        // test to see if gym already appeared on the list    

        if (positionsArr.includes(gymLat)) { 
            athleteName = dataLocations[i]["Name"];
            athleteRank = dataLocations[i]["Rank"];
            
            let pos = positionsArr.indexOf(gymLat);
            newContentString =      
                '<div id="extra-athlete">'     
                + '<p id="name-athlete">' + athleteRank + '. ' + athleteName + '</p>'
                + '</div>';

            existContentString = contentArr[pos];
            finContentString = existContentString + newContentString;
            contentArr[pos] = finContentString;

            infoArr[pos] = new google.maps.InfoWindow({
                content: finContentString,
            });

        } else {
            positionsArr.push(gymLat);
            gymPosition = dataLocations[i]["Location"];
            gymName = dataLocations[i]["Gym"];
            athleteName = dataLocations[i]["Name"];
            athleteRank = dataLocations[i]["Rank"];

            contentString = 
              '<div id = "region-info">'
              + '<p id="name-gym">Gym: ' + gymName + '</p>'
              + '<p id="name-athlete">' + athleteRank + '. ' + athleteName + '</p>'
              + '</div>';
            contentArr.push(contentString);

        	infoWindow = new google.maps.InfoWindow({
        		content: contentString,
        	});
        	infoArr.push(infoWindow);
            
            // add the marker to the map
            marker = new google.maps.Marker({
                position: gymPosition,
                //icon: pinIcon,
                map: map
            });

            markerArr.push(marker); // add marker to markers array

            for(let j = 0; j < markerArr.length; j++) {
            	markerArr[j].addListener("click", () => {
        	      if (infoWindow) {
        	      	for (let k = 0; k < infoArr.length; k++){
        	      		infoArr[k].close();
        	      	}
        	      }
                    infoArr[j].open(map, markerArr[j]);
            	});	
            }	
        }
    }

}

