/*
 * Copyright 2002-2013 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.springframework.samples.petclinic.visit;

import org.springframework.web.bind.annotation.RestController;

@RestController
public class VisitController {

    /*private final VisitRepository visits;
    private final PetRepository pets;


    public VisitRepository getVisits() {
        return visits;
    }

    @Autowired
    public VisitController(VisitRepository visits, PetRepository pets) {
        this.visits = visits;
        this.pets = pets;
    }

    // Spring MVC calls method loadPetWithVisit(...) before processNewVisitForm is called
    @RequestMapping(value = "/owners/{ownerId}/pets/{petId}/visits/", method = RequestMethod.POST)
    public void addVisit(Visit visit) {
        this.visits.save(visit);
    }*/

}
