document.addEventListener('DOMContentLoaded', function() {
    Array.from(document.getElementsByClassName('admin-numeric-filter-slider')).forEach(function(slider) {
        var from = parseFloat(slider.closest('.admin-numeric-filter-wrapper').querySelectorAll('.admin-numeric-filter-wrapper-group input')[0].value);
        var to = parseFloat(slider.closest('.admin-numeric-filter-wrapper').querySelectorAll('.admin-numeric-filter-wrapper-group input')[1].value);
	console.log(to)
	console.log(from)

        noUiSlider.create(slider, {
            start: [from, to],
            step: parseFloat(slider.getAttribute('data-step')),
            connect: true,
            format: wNumb({
                decimals: parseFloat(slider.getAttribute('data-decimals'))
            }),
            range: {
                'min': parseFloat(slider.getAttribute('data-min')),
                'max': parseFloat(slider.getAttribute('data-max'))
            }
        });

	var convertValuesToTime = function(values,handle){
  		var hours = 0,minutes = 0;
      
  		//if(handle === 0){
  		hours_first = convertToHour(values[0]);
    		minutes_first = convertToMinute(values[0],hours_first);
  			//leftValue.innerHTML = formatHoursAndMinutes(hours,minutes);
    			//return formatHoursAndMinutes(hours,minutes);
  		//};
  
  		hours = convertToHour(values[1]);
  		minutes = convertToMinute(values[1],hours);
 		//rightValue.innerHTML = formatHoursAndMinutes(hours,minutes);
		return [formatHoursAndMinutes(hours_first,minutes_first),formatHoursAndMinutes(hours,minutes)];
    
	};

	var convertToHour = function(value){
		return Math.floor(value / 60);
	};
	var convertToMinute = function(value,hour){
		return value - hour * 60;
	};
	var formatHoursAndMinutes = function(hours,minutes){
		if(hours.toString().length == 1) hours = '0' + hours;
  			if(minutes.toString().length == 1) minutes = '0' + minutes;
    				return hours+':'+minutes;
	};


        slider.noUiSlider.on('update', function(values, handle) {                        
            var parent = this.target.closest('.admin-numeric-filter-wrapper');
            var from = parent.querySelectorAll('.admin-numeric-filter-wrapper-group input')[0];
            var to = parent.querySelectorAll('.admin-numeric-filter-wrapper-group input')[1];
	    console.log(from)
	    console.log(to)
	    
	    if(to.name === 'average_length_to'){
	    	var values_test = convertValuesToTime(values,handle);
	    	if(handle === 0){
			console.log('Test')
			console.log(values[0])
	    	}else{
	        	console.log(values[1])
	    	};
	
            	//if(handle === 0){
            	parent.querySelectorAll('.admin-numeric-filter-slider-tooltip-from')[0].innerHTML = values_test[0];
		from.value = values[0]
		console.log("Test2")
	    	//}else{
            	parent.querySelectorAll('.admin-numeric-filter-slider-tooltip-to')[0].innerHTML = values_test[1];
		to.value = values[1]
	    	//};
	    }else{
		parent.querySelectorAll('.admin-numeric-filter-slider-tooltip-from')[0].innerHTML = values[0];
		parent.querySelectorAll('.admin-numeric-filter-slider-tooltip-to')[0].innerHTML = values[1];
		from.value = values[0]
		to.value = values[1]
	    };

	    console.log(values[0])
	    console.log(values[1])

            //from.value = values[0]
            //to.value = values[1]
        });
    });
});
